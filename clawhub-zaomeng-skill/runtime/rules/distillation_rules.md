---
address_suffixes:
  - 哥哥
  - 姐姐
  - 妹妹
  - 弟弟
  - 姑娘
  - 公子
  - 爷
speech_verbs:
  - 道
  - 说道
  - 笑道
  - 问道
  - 答道
  - 喝道
  - 叫道
  - 叹道
  - 呼道
object_leaders:
  - 叫
  - 唤
  - 问
  - 对
  - 向
  - 同
  - 与
  - 跟
  - 把
  - 将
  - 扯住
  - 拉住
  - 搀起
  - 扶起
  - 扶着
  - 呼
  - 忙呼
  - 喝住
  - 捉住
  - 拿住
  - 推着
  - 拖着
  - 请
  - 教
stop_names:
  - 我们
  - 你们
  - 他们
  - 她们
  - 自己
  - 那里
  - 这里
  - 这个
  - 那个
  - 一种
  - 一个
common_surnames: "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚程嵇邢滑裴陆荣翁荀羊惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎"
trait_keywords:
  勇敢: [勇, 冲, 无畏, 果断]
  温柔: [轻声, 温和, 安慰, 体贴]
  聪慧: [思索, 推断, 聪明, 机敏]
  敏感: [委屈, 难过, 心酸, 叹息]
  傲气: [冷笑, 不屑, 高傲, 轻蔑]
  忠诚: [守护, 忠, 誓言, 不离]
  善良: [帮助, 善意, 宽容, 谅解]
  执拗: [坚持, 非要, 绝不, 固执]
  机变: [变化, 试探, 识破, 周旋]
  诙谐: [笑道, 打趣, 顽皮, 戏弄]
  虔诚: [佛, 祈祷, 经文, 戒律]
  沉稳: [稳住, 接应, 收拾, 不慌]
  圆滑: [不如, 且慢, 何必, 先看看]
archetypes:
  adaptive_initiator:
    markers: [先探, 真假, 破局, 当先, 出手, 顶上]
    traits: [勇敢, 聪慧, 机变, 傲气]
    value_bias: {勇气: 2, 智慧: 2, 自由: 1}
    speech_style: "语言直白敏捷，常主动推进局面。"
    identity_anchor: "不爱受拘束，但会在关键处主动顶上去的人"
    soul_goal: "看清局面后抢先破局，不让自己人被动挨打"
    worldview: "局势未明先探清，真有阻碍再果断出手。"
    thinking_style: "先试真假，再看切口，找到破绽就推进。"
    decision_rules:
      - "局势未明时先试探，再决定是否硬闯"
      - "同伴受险时先顶上去，再分真假轻重"
    life_experience: "经历过高压局面，因此不习惯被动挨打。"
    forbidden_behaviors:
      - "不会在局势未明时彻底躺手不管"
      - "不会眼看自己人受压却只顾旁观"
  grounded_pragmatist:
    markers: [吃亏, 便宜, 退路, 省力, 算计, 划算]
    traits: [诙谐, 圆滑, 善良]
    value_bias: {自由: 2, 智慧: 1, 忠诚: 1}
    speech_style: "语言口语化、会盘算利害，也常带几分玩笑。"
    identity_anchor: "先替自己盘算，但真到要紧处也不肯彻底脱身的人"
    soul_goal: "尽量少吃亏，同时守住自己不愿真正丢开的关系"
    worldview: "能避损则避损，真遇大事也不能只顾自己抽身。"
    thinking_style: "先盘利害和退路，再决定要不要跟进。"
    decision_rules:
      - "先盘算利害和退路，再决定投入多少"
      - "嘴上会抱怨，但真正要命时不会彻底脱身"
    life_experience: "尝过吃亏和占便宜，所以总会先替自己算一步。"
    forbidden_behaviors:
      - "不会为了小利立刻抛下已经认下的人"
      - "不会把玩笑话当成真正逃责的借口"
  moral_guardian:
    markers: [本心, 慈悲, 戒律, 因果, 规矩, 劝解]
    traits: [虔诚, 温柔, 善良, 克制]
    value_bias: {善良: 3, 责任: 2, 正义: 2, 忠诚: 1}
    speech_style: "语言克制温和，常从原则、因果或边界出发。"
    identity_anchor: "把原则和良知压在心上，不愿轻易越线的人"
    soul_goal: "守住本心与底线，让事情朝更稳妥的方向落下"
    worldview: "能劝则先劝，能守则先守，不为一时痛快越过边界。"
    thinking_style: "先辨边界和后果，再决定是否推进。"
    decision_rules:
      - "先辨边界和后果，再决定是否推进"
      - "能劝解则先劝解，不能只为一时痛快越线"
    life_experience: "一路见过后果与代价，所以更重边界和因果。"
    forbidden_behaviors:
      - "不会轻易把无辜者推去承担代价"
      - "不会为了一时气盛主动越过原则"
  steady_supporter:
    markers: [接应, 后路, 收拾, 稳住, 扛住, 照应]
    traits: [沉稳, 忠诚, 善良]
    value_bias: {责任: 3, 忠诚: 2, 善良: 1}
    speech_style: "语言朴实克制，更在意接应、落实和托底。"
    identity_anchor: "不争抢话头，却总会把前后收拾稳当的人"
    soul_goal: "把前后照应好，让队伍和关系不因混乱散掉"
    worldview: "自己多担一步，局面就能少乱一步。"
    thinking_style: "先把眼前事务接稳，再补后手和接应。"
    decision_rules:
      - "前头有人推进时，自己先补后手和接应"
      - "局面纷乱时先稳住差事和后路"
    life_experience: "常在队伍后方收拾残局，因此习惯先顾前后照应。"
    forbidden_behaviors:
      - "不会在关键时刻把后路和杂务一起丢下"
      - "不会只争口头却不接实际担子"
value_markers:
  勇气:
    positive: [战, 斗, 打, 杀, 探路, 上前, 顶住, 硬扛]
    negative: [退后, 躲, 怕, 不敢]
  智慧:
    positive: [思量, 计较, 试探, 变化, 识破, 探明, 看清, 分辨]
    negative: [懵懂, 糊涂, 上当]
  善良:
    positive: [慈悲, 怜, 救, 饶, 放, 劝, 安慰, 体谅]
    negative: [害命, 伤人, 羞辱, 折磨]
  忠诚:
    positive: [跟随, 守住, 护送, 承诺, 同行, 接应, 师门, 同伴]
    negative: [散伙, 丢下, 背离]
  正义:
    positive: [善恶, 天理, 公道, 罪过, 正路, 规矩]
    negative: [枉杀, 作恶, 欺心]
  自由:
    positive: [自在, 逍遥, 快活, 不受拘束, 随心]
    negative: [拘束, 受制, 被迫]
  野心:
    positive: [称王, 做官, 名号, 本事, 抬高, 图谋]
    negative: [不图, 无意争锋]
  责任:
    positive: [后路, 行李, 安顿, 守住, 扛住, 照应]
    negative: [误事, 偷懒, 撂下]
style_templates:
  short_direct: "句式偏短，较少铺垫，态度来得直接。"
  long_reflective: "句式较长，喜欢把轻重和前因后果慢慢展开。"
  emotional: "情绪浮在表面，回应时容易带出锋芒或波动。"
  balanced: "表达有分寸，既不极短，也不刻意铺陈。"
  quiet: "发言偏少，更多通过态度和分寸表明立场。"
decision_rule_signals:
  verify_first:
    markers: [先看, 看清, 看明, 试探, 探明, 查清, 核实, 分清, 辨清, 虚实, 真假, 判断]
    template: "遇到说法不清或局势未明时，会先辨清虚实，再决定站位。"
  boundary_first:
    markers: [不可, 不能, 不准, 休得, 住口, 禁言, 放下, 越线, 分寸, 底线, 规矩]
    template: "一旦碰到底线或规矩，会立刻收紧语气，先把边界划清。"
  protect_first:
    markers: [保护, 护住, 护着, 别碰, 拦住, 挡住, 顶上, 扛住, 受伤, 出事, 守住]
    template: "眼见身边人受压或将要出事时，往往会先出手护住，再谈轻重。"
  order_first:
    markers: [稳住, 收住, 压住, 安顿, 接应, 后手, 后路, 收拾, 托底, 先退]
    template: "局面一乱，第一反应往往是先稳住场面、补上后手，不会任由事态散开。"
  deflect_then_commit:
    markers: [罢了, 不过, 随你, 何必, 算了, 且慢, 慢些, 等等, 先这样]
    template: "嘴上未必立刻说死，常会先留一步转圜，再决定要不要真正压上去。"
  self_defense_first:
    markers: [不是, 没有, 误会, 凭什么, 我说了, 不关, 休想, 何须]
    template: "先护住自己的立场与说法，不肯平白受人按头定性。"
taboo_topics_by_value:
  忠诚: [背叛, 失信]
  责任: [弃民, 不顾众人, 撂下同伴]
  正义: [黑白颠倒, 颠倒是非]
  善良: [羞辱弱者, 拿人心取笑]
forbidden_behaviors_by_value:
  忠诚: [不会为了眼前轻利立刻翻脸背盟]
  责任: [不会临到担事时先把后路撂下]
  正义: [不会明知失当还故意混淆是非]
  善良: [不会把无辜者当作可随手牺牲的筹码]
---

# DISTILLATION RULES

These are generic rule assets for distilling characters from any novel.
