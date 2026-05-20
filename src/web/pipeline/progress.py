from __future__ import annotations

from typing import Any, Callable

from src.web.run_ops.state import project_manifest_summary


def apply_distill_progress(
    current: dict[str, Any],
    *,
    stage: str,
    payload: dict[str, Any],
    utc_now: Callable[[], str],
    update_manifest_chunk_progress: Callable[..., None],
) -> None:
    progress = current.setdefault("progress", {})
    if stage == "text_loaded":
        progress["stage"] = "text_loaded"
        progress["message"] = "已载入小说文本"
    elif stage == "characters_ready":
        progress["stage"] = "characters_ready"
        total = int(payload.get("total", 0) or 0)
        progress["message"] = f"已锁定 {total} 个待蒸馏角色" if total else "已锁定待蒸馏角色"
    elif stage == "drafting_character":
        progress["stage"] = "distilling"
        progress["current_character"] = payload.get("character", "")
        progress["message"] = f"正在蒸馏 {payload.get('character', '')}"
    elif stage == "materializing_character":
        progress["stage"] = "distilling"
        progress["current_character"] = payload.get("character", "")
        progress["message"] = f"正在落盘 {payload.get('character', '')}"
    elif stage == "chunking_character":
        progress["stage"] = "distilling"
        progress["current_character"] = payload.get("character", "")
        index = int(payload.get("chunk_index", 0) or 0)
        total = int(payload.get("chunk_total", 0) or 0)
        workers = int(payload.get("parallel_workers", 1) or 1)
        worker_suffix = f"，并行 {workers} 线程" if workers > 1 else ""
        progress["message"] = f"正在分批蒸馏 {payload.get('character', '')}（{index}/{total}）{worker_suffix}"
        update_manifest_chunk_progress(
            current,
            capability="distill",
            mode="chunked",
            chunk_count=total,
            current_chunk=index,
            current_label=str(payload.get("chunk_label", "")).strip(),
            status="running",
            merge_required=True,
            merge_status="pending",
        )
    elif stage == "merging_character":
        progress["stage"] = "distilling"
        progress["current_character"] = payload.get("character", "")
        progress["message"] = f"正在汇总 {payload.get('character', '')} 的分批草稿"
        update_manifest_chunk_progress(
            current,
            capability="distill",
            mode="chunked",
            chunk_count=int(payload.get("chunk_total", 0) or 0) or None,
            current_chunk=int(payload.get("chunk_total", 0) or 0) or None,
            current_label=f"{payload.get('character', '')} 汇总",
            status="complete",
            merge_required=True,
            merge_status="running",
        )
    elif stage == "character_done":
        progress["stage"] = "distilling"
        character = str(payload.get("character", "")).strip()
        completed = [str(item).strip() for item in progress.get("completed_characters", []) if str(item).strip()]
        if character and character not in completed:
            completed.append(character)
        progress["completed_characters"] = completed
        progress["completed_count"] = len(completed)
        progress["current_character"] = ""
        progress["message"] = f"{character} 蒸馏完成"

    current.setdefault("events", []).append(
        {
            "stage": stage,
            "status": "running",
            "message": progress.get("message", ""),
            "character": payload.get("character", ""),
            "capability": "distill",
            "timestamp": utc_now(),
        }
    )
    current["updated_at"] = utc_now()


def apply_relation_progress(
    current: dict[str, Any],
    *,
    stage: str,
    payload: dict[str, Any],
    utc_now: Callable[[], str],
    update_manifest_chunk_progress: Callable[..., None],
) -> None:
    progress = current.setdefault("progress", {})
    if stage == "rendering_graph":
        progress["stage"] = "rendering_graph"
        progress["graph_status"] = "running"
        progress["message"] = "正在生成人物关系图谱"
    elif stage == "chunking_graph":
        progress["stage"] = "rendering_graph"
        progress["graph_status"] = "running"
        index = int(payload.get("chunk_index", 0) or 0)
        total = int(payload.get("chunk_total", 0) or 0)
        workers = int(payload.get("parallel_workers", 1) or 1)
        worker_suffix = f"，并行 {workers} 线程" if workers > 1 else ""
        progress["message"] = f"正在分批抽取人物关系（{index}/{total}）{worker_suffix}"
        update_manifest_chunk_progress(
            current,
            capability="relation",
            mode="chunked",
            chunk_count=total,
            current_chunk=index,
            current_label=str(payload.get("chunk_label", "")).strip(),
            status="running",
            merge_required=True,
            merge_status="pending",
        )
    elif stage == "merging_graph":
        progress["stage"] = "rendering_graph"
        progress["graph_status"] = "running"
        progress["message"] = "正在汇总分批关系草稿"
        update_manifest_chunk_progress(
            current,
            capability="relation",
            mode="chunked",
            chunk_count=int(payload.get("chunk_total", 0) or 0) or None,
            current_chunk=int(payload.get("chunk_total", 0) or 0) or None,
            current_label="关系汇总",
            status="complete",
            merge_required=True,
            merge_status="running",
        )
    elif stage == "graph_done":
        progress["stage"] = "graph_done"
        progress["graph_status"] = "complete"
        progress["message"] = "人物关系图谱已生成"

    current.setdefault("events", []).append(
        {
            "stage": stage,
            "status": "running",
            "message": progress.get("message", ""),
            "character": "",
            "capability": "export_graph",
            "timestamp": utc_now(),
        }
    )
    current["updated_at"] = utc_now()


def finalize_workflow_success(
    refreshed: dict[str, Any],
    *,
    utc_now: Callable[[], str],
    finalize_manifest_timing: Callable[[dict[str, Any], str], None],
) -> None:
    refreshed["status"] = "ready"
    refreshed["success"] = True
    refreshed["updated_at"] = utc_now()
    finalize_manifest_timing(refreshed, "completed")
    refreshed.setdefault("summary", {})
    refreshed.setdefault("capabilities", {})["distill"] = {
        "status": "complete",
        "success": True,
        "updated_at": utc_now(),
        "message": "canonical profiles generated",
    }
    refreshed["capabilities"]["materialize"] = {
        "status": "complete",
        "success": True,
        "updated_at": utc_now(),
        "message": "persona bundle written",
    }
    refreshed["capabilities"]["export_graph"] = {
        "status": "complete",
        "success": True,
        "updated_at": utc_now(),
        "message": "relation graph exported",
    }
    refreshed["capabilities"]["verify_workflow"] = {
        "status": "complete",
        "success": True,
        "updated_at": utc_now(),
        "message": "automatic workflow finished",
    }
    refreshed.setdefault("events", []).append(
        {
            "stage": "workflow_complete",
            "status": "complete",
            "message": f"本次整理耗时 {refreshed['timing']['elapsed_text']}" if refreshed.get("timing", {}).get("elapsed_text") else "本次整理已完成",
            "character": "",
            "capability": "verify_workflow",
            "timestamp": utc_now(),
        }
    )
    project_manifest_summary(refreshed)


def finalize_workflow_success_without_graph(
    refreshed: dict[str, Any],
    *,
    graph_error: str,
    utc_now: Callable[[], str],
    finalize_manifest_timing: Callable[[dict[str, Any], str], None],
) -> None:
    refreshed["status"] = "ready"
    refreshed["success"] = True
    refreshed["updated_at"] = utc_now()
    finalize_manifest_timing(refreshed, "completed")
    refreshed.setdefault("summary", {})

    progress = refreshed.setdefault("progress", {})
    progress["graph_status"] = "failed"
    progress["stage"] = "graph_failed"
    progress["current_character"] = ""
    progress["message"] = f"人物蒸馏已完成，关系图谱生成失败：{graph_error}"

    refreshed.setdefault("capabilities", {})["distill"] = {
        "status": "complete",
        "success": True,
        "updated_at": utc_now(),
        "message": "canonical profiles generated",
    }
    refreshed["capabilities"]["materialize"] = {
        "status": "complete",
        "success": True,
        "updated_at": utc_now(),
        "message": "persona bundle written",
    }
    refreshed["capabilities"]["export_graph"] = {
        "status": "failed",
        "success": False,
        "updated_at": utc_now(),
        "message": graph_error,
    }
    refreshed["capabilities"]["verify_workflow"] = {
        "status": "complete",
        "success": True,
        "updated_at": utc_now(),
        "message": "automatic workflow finished without relation graph",
    }
    refreshed.setdefault("events", []).append(
        {
            "stage": "graph_failed",
            "status": "failed",
            "message": f"关系图谱生成失败：{graph_error}",
            "character": "",
            "capability": "export_graph",
            "timestamp": utc_now(),
        }
    )
    project_manifest_summary(refreshed)
    refreshed.setdefault("events", []).append(
        {
            "stage": "workflow_complete",
            "status": "complete",
            "message": (
                f"人物已可入场，关系图未生成；本次整理耗时 {refreshed['timing']['elapsed_text']}"
                if refreshed.get("timing", {}).get("elapsed_text")
                else "人物已可入场，关系图未生成。"
            ),
            "character": "",
            "capability": "verify_workflow",
            "timestamp": utc_now(),
        }
    )


def finalize_workflow_stopped(
    stopped: dict[str, Any],
    *,
    message: str,
    utc_now: Callable[[], str],
    finalize_manifest_timing: Callable[[dict[str, Any], str], None],
) -> None:
    stopped["status"] = "stopped"
    stopped["success"] = False
    stopped["updated_at"] = utc_now()
    finalize_manifest_timing(stopped, "stopped")
    stopped.setdefault("summary", {})
    progress = stopped.setdefault("progress", {})
    progress["stage"] = "stopped"
    progress["message"] = message
    control = stopped.setdefault("control", {})
    if not str(control.get("stop_acknowledged_at", "")).strip():
        control["stop_acknowledged_at"] = utc_now()
    stopped.setdefault("capabilities", {})["verify_workflow"] = {
        "status": "stopped",
        "success": False,
        "updated_at": utc_now(),
        "message": "automatic workflow stopped by user",
    }
    stopped.setdefault("events", []).append(
        {
            "stage": "stopped",
            "status": "stopped",
            "message": message,
            "character": str(progress.get("current_character", "")).strip(),
            "capability": "verify_workflow",
            "timestamp": utc_now(),
        }
    )
    if stopped.get("timing", {}).get("elapsed_text"):
        stopped.setdefault("events", []).append(
            {
                "stage": "stopped_timing",
                "status": "stopped",
                "message": f"本次整理已停止，已耗时 {stopped['timing']['elapsed_text']}",
                "character": "",
                "capability": "verify_workflow",
                "timestamp": utc_now(),
            }
        )
    project_manifest_summary(stopped)


def finalize_workflow_failed(
    failed: dict[str, Any],
    *,
    message: str,
    utc_now: Callable[[], str],
    finalize_manifest_timing: Callable[[dict[str, Any], str], None],
) -> None:
    failed["status"] = "failed"
    failed["success"] = False
    failed["updated_at"] = utc_now()
    finalize_manifest_timing(failed, "failed")
    failed.setdefault("summary", {})
    failed.setdefault("progress", {})["message"] = message
    failed.setdefault("events", []).append(
        {
            "stage": "failed",
            "status": "failed",
            "message": message,
            "character": "",
            "capability": "verify_workflow",
            "timestamp": utc_now(),
        }
    )
    if failed.get("timing", {}).get("elapsed_text"):
        failed.setdefault("events", []).append(
            {
                "stage": "failed_timing",
                "status": "failed",
                "message": f"本次整理已中断，已耗时 {failed['timing']['elapsed_text']}",
                "character": "",
                "capability": "verify_workflow",
                "timestamp": utc_now(),
            }
        )
    project_manifest_summary(failed)
