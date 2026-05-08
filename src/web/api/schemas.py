from __future__ import annotations

from pydantic import BaseModel, Field


class CreateRunRequest(BaseModel):
    novel_name: str = Field(..., min_length=1)
    novel_content_base64: str = Field(..., min_length=1)
    characters: list[str] = Field(default_factory=list, min_length=1)
    max_sentences: int = Field(default=120, ge=20, le=300)
    max_chars: int = Field(default=50_000, ge=2_000, le=200_000)
    auto_run: bool = Field(default=False)


class RestartRunRequest(BaseModel):
    characters: list[str] = Field(default_factory=list)
    novel_name: str = Field(default="")
    novel_content_base64: str = Field(default="")
    max_sentences: int = Field(default=120, ge=20, le=300)
    max_chars: int = Field(default=50_000, ge=2_000, le=200_000)


class SaveModelSettingsRequest(BaseModel):
    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    base_url: str = Field(default="")
    api_key: str = Field(default="")
    max_tokens: int = Field(default=0, ge=0, le=16000)


class IngestCharacterRequest(BaseModel):
    character: str = Field(..., min_length=1)
    content_base64: str = Field(..., min_length=1)
    filename: str = Field(default="PROFILE.generated.md")


class IngestRelationRequest(BaseModel):
    content_base64: str = Field(..., min_length=1)
    filename: str = Field(default="relations.md")


class SavePersonaReviewRequest(BaseModel):
    core_identity: str = Field(default="")
    story_role: str = Field(default="")
    identity_anchor: str = Field(default="")
    temperament_type: str = Field(default="")
    soul_goal: str = Field(default="")
    hidden_desire: str = Field(default="")
    inner_conflict: str = Field(default="")
    self_cognition: str = Field(default="")
    private_self: str = Field(default="")
    speech_style: str = Field(default="")
    cadence: str = Field(default="")
    typical_lines: str = Field(default="")
    signature_phrases: str = Field(default="")
    sentence_openers: str = Field(default="")
    sentence_endings: str = Field(default="")
    social_mode: str = Field(default="")
    thinking_style: str = Field(default="")
    decision_rules: str = Field(default="")
    reward_logic: str = Field(default="")
    worldview: str = Field(default="")
    belief_anchor: str = Field(default="")
    moral_bottom_line: str = Field(default="")
    restraint_threshold: str = Field(default="")
    core_traits: str = Field(default="")
    key_bonds: str = Field(default="")
    forbidden_behaviors: str = Field(default="")
    stress_response: str = Field(default="")
    emotion_model: str = Field(default="")
    anger_style: str = Field(default="")
    joy_style: str = Field(default="")
    grievance_style: str = Field(default="")
    others_impression: str = Field(default="")


class CreateDialogueSessionRequest(BaseModel):
    mode: str = Field(..., pattern="^(act|insert|observe)$")
    participants: list[str] = Field(default_factory=list)
    controlled_character: str = Field(default="")
    self_profile: dict[str, str] = Field(default_factory=dict)


class PrepareDialogueTurnRequest(BaseModel):
    message: str = Field(..., min_length=1)


class SuggestDialogueTurnRequest(BaseModel):
    seed_text: str = Field(default="")


class DialogueResponseItem(BaseModel):
    speaker: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class IngestDialogueTurnRequest(BaseModel):
    responses: list[DialogueResponseItem] = Field(default_factory=list, min_length=1)
