# 英文格式与篇幅

## 先分清语言阶段

默认先按 [中文开发与英文定稿](chinese-to-english.md) 交中文开发剧本，使用清楚的中文集场、动作、角色和对白格式；地点与人物行为仍服从目标英语市场。下文Fountain子集、英文W和PDF助手用于英文阶段。中文稿的集数、约定计字口径/范围及完成状态独立记录，未生成英文时W只有预算、没有达标结论，也没有固定中英换算比例。

中文阶段若需Word/PDF，使用支持中文字体的文档工具实际生成并检查；不能把中文交给下文WinAnsi字体的英文PDF助手。已有英文稿的局部审改可直接使用英文工具。用户指定其它格式时以实际模板为准。

## 项目格式

优先用户/制片方实际模板。没有模板时采用清楚的英文 screenplay 习惯：INT./EXT. 场景标题、现在时动作、独立角色提示与对白，括号指示只在表演含义不清时使用。首次出场可大写姓名并给简洁可拍特征；镜头指令只保留叙事所需。O.S. 与 V.O. 按场外发声/画外音区分，全稿统一。

正式排版可用12pt Courier类等宽字体作为起点，再服从交付要求；英文页数不是片长保证。开发审稿用集场ID方便反馈，投稿净稿是否显示场号依实际要求。不要将拍摄稿的技术标注强加于所有投稿稿。[Academy 格式示例](https://www.oscars.org/sites/oscars/files/scriptsample.pdf)用于常见排版参考，不是短剧平台统一标准。

开发源稿默认使用 [Fountain](https://fountain.io/syntax/) 的纯文本标记子集，便于统计和明确转换：`# Episode 1` 是内部集标题，`@NAME` 是强制角色提示，`!` 可强制动作，场号放在场景标题末尾的 `#1-1#` 中。标准Fountain的`#`分节在打印时不可见，不能直接假定集名会导出。本技能PDF助手将其转换成可见标题；其它软件需映射到可打印的Episode/标题元素并检查。来源核查日：2026-10-14。

```text
Title: LAST KEY
Credit: Written by
Author: [writer name]

# Episode 1 - The Drawer

INT. REPAIR SHOP - NIGHT #1-1#

MAYA, 28, locks the front door. A key drops from Jonah's coat.

@MAYA
That's mine.

@JONAH
(not turning)
Then why does it open my car?

!MAYA DOES NOT MOVE.
```

示例只展示格式，不代表一集应有的完整长度。写在画面上的短信/标牌用动作段的 `ON SCREEN:` 或 `INSERT:` 描述；信息仍计入正文。

## N、W 与时长

- N = 约定集数。W 默认是英文**正文总词数**：动作 + 对白 + 括号指示；不含标题页、集名、场标题、角色提示、转场、批注、大纲和审核报告。用户用其他口径则记录并遵守，不能悄悄替换。
- 单集基准 W/N 仅用于预算。依该集事件量分配不同权重，整数取整后的差额分配到有承载空间的集，使总和恰为 W。容差由约定决定，不能把建议的容差当已同意。
- 单集预算表包含集号、剧情功能、目标词数、对白估算、动作/停顿时长、核心变化、回报/钩子、下一集兑现和实写词数。
- 不将“中文字数”按固定比例换成英文 words；不把电影的一页一分钟套给微短剧。
- 片长估计拆为对白发声 + 动作/反应 + 镜头停留；重叠发生的部分不能重复累加。先用一段实际计时试读校准语速，再检查无对白场景。没做计时只能给估计区间和假设。
- 如果 N、W 和目标时长冲突，给出改集数、改篇幅或改时长的具体选择。压缩时先删重复信息、合并同功能场景；扩写增加有后果的选择与反应，不用空泛对白凑词。

## 统计助手

Python 3 标准库，无外部依赖。在 skill 目录执行，脚本路径也可用绝对路径：

```text
python scripts/script_metrics.py manuscript.fountain --expected-episodes 60 --target-words 18000 --tolerance 0.05 --json metrics.json
```

数字仅是命令示例，不是北美短剧默认要求。分批稿从第21集开始可加 `--start-episode 21 --expected-episodes 5`；目标词数必须相应为该批目标。退出码0为结构/指定数字检查通过，1为检查问题，2为输入/参数错误。没有提供的预算显示 `not_checked`，不能解释为已满足约定。

助手要求：每集独立 `# Episode N` 行；每个新场独立 INT./EXT./EST./INT./EXT./INT/EXT/I/E 场标题行；每段对白首行使用 `@角色名`；段与段空行隔开。场号可省略；有场号时不能重复。章节标题必须独立成段。括号指示在对白段内独立一行；裸大写角色提示会报需规范化，避免误计为动作。

支持忽略 `[[批注]]`、`/*隐藏块*/`、标题页、转场、Fountain分节/梗概标记和分页符；含 `[[...]]` 的文字确实不计数，不能拿它包裹实际正文。数字算词，英语缩写/连字符词按一个词，破折号分词；小数/带逗号数字整体算一个词。非拉丁连续文本会提示需人工核对英语口径。

它只支持上述子集，不是完整Fountain解析器。不支持双列同时对白、居中源稿标题、歌词标记、行内强调、混合文档、PDF/OCR/Word直接输入；遇到不支持标记会报告。先制作结构化统计副本并核对与正文一致，不为让检查通过而删掉正文。其它格式可用适配该格式的可靠计数方法，写清口径。

定稿同时报告各集正文/对白/动作/括号词数与全稿合计；数据异常先查解析和格式，再改稿。词数工具不能证明对白自然、钩子有效、合法或时长准确。最后渲染版再检查场标题与角色/对白分页、页码、缺字、重复集和结尾截断。

修改段落或插入空行后，核对每句对白仍属于正确的`@角色`段。没有提示的普通英语段落会被解析为动作；即使总词数和结构通过，漏标对白也可能使分类和版式错误。这一项需要正文/导出对照，不能只看工具的通过标记。

只审改独立场景且没有集数约定时，可在统计副本临时加`# Episode 1 - Scene Sample`作为解析容器；明确它不是已完成一集，不混入原项目集数，也不将临时集名强加到用户净稿。仅报该场词数，未约定的预算留空；或使用适合单场的计数方法。无需为工具扩写完整系列。

## 同场跨集与批次上下文

新集直接出现正文时，助手继承上一集最后的场景；不新增真实场次。为了让审稿意图更明确，可在新集标题后单独写 `[[CONTINUE SCENE: 1-1]]`，ID必须是紧邻的活动场景。该注释是本技能内部约定，不是标准Fountain续场语法。换地点或发生需要新场的时间变化时仍写真实新场标题。

```text
# Episode 1 - The Key

INT. SHOP - NIGHT #1-1#

@MAYA
Who gave you that?

# Episode 2 - The Answer

[[CONTINUE SCENE: 1-1]]

@JONAH
Your sister. Ask her why.
```

这段是两集片段、一个新建场景、两个分集场景段落。指标 `scenes` 数输入中的新场标题，`scene_segments` 包含跨集接续段，`continued_scene` 保存继承来源。统计不能推断相同地点是否真正连续，仍需人工核对时间与行动。

只统计/导出后半批且首集续前场时，提供上一批真实末场，例如 `--initial-scene "INT. SHOP - NIGHT #20-3#" --start-episode 21`。输入这个参数等于声明上下文已核对，不能为了消除报错而编造；批内新场次数不包括此前已开始的场。整稿不能靠重复同一场号虚增场次。

## 逐集预算

约定逐集预算时另存JSON，调用加 `--episode-budgets budgets.json`：

```json
{
  "scope": "batch",
  "episodes": [
    {"episode": 1, "target_words": 280, "tolerance": 0.05},
    {"episode": 2, "target_words": 320, "tolerance": 0.03}
  ]
}
```

每行省略容差时继承命令的 `--tolerance`（默认0）；总量容差仍单独采用命令值。`batch`要求预算集号恰好覆盖当前期望范围；`project`允许整剧预算表用于一个批次，只检查该批，每集目标之和须与提供的该批总目标一致。缺项、重复项、预算和总目标冲突均报告，不能事后把目标改成实写数冒充达标。总量正确而某集4词、另一集96词，在约定各50词时仍失败。

输出 `checks` 分列结构、总量、逐集预算及未执行的创作/真人/发行/渲染检查。`passed`只汇总机器可查项。检查口径不能覆盖未给出的单集时长、法律或质量要求。

## 源稿、审稿与净稿导出

| 元素 | 开发源稿 | 审稿PDF | 净稿PDF |
|---|---|---|---|
| 集 | `# Episode N - Subtitle` | 可见集标题 | 可见集标题 |
| 场 | 场标题及可选`#ID#` | 场标题并显示ID | 场标题，不显示内部ID |
| 同场续集 | 继承场景，可加续场注释 | 续场标题及原ID | 续场标题与`(CONTINUED)`，不是新场 |
| 台词/动作 | `@`、可选`!` | 去除标记后排版 | 去除标记后排版 |
| 批注/梗概/隐藏块 | 可保留在源文件 | 不混入正文，另交审稿表 | 不导出 |

通用PDF助手 [export_screenplay.py](../scripts/export_screenplay.py) 与统计共用解析结果，支持Letter、12pt Courier、可见集标题、场景/角色/对白分层与页码。需要Python和ReportLab；统计助手仍无外部依赖。

```text
python scripts/export_screenplay.py manuscript.fountain --output screenplay.pdf --title "LAST KEY"
```

审稿加 `--review` 显示场号；实际模板需要每集另起页时加 `--episode-page-break`。已有输出须换路径或明确加 `--force`；不能覆盖源稿。先按约定执行统计检查，再导出并逐页渲染检查；导出成功本身不代表预算或审稿通过。内置Courier只处理WinAnsi字符；其它文字、复杂样式或跨页长独白改用有字体支持和续页规则的剧本排版器，不删改语言只为适配助手。

助手不导出Word/FDX、不自动复制标题页署名或联系信息，也不声称符合ReelShort专用模板。需要这些格式时按实际模板映射同一正文到相应文档工具，显式设置集标题和续场、按用户提供信息填写署名，再实际生成并渲染。没有平台模板时只称通用开发稿。Final Draft的不同模板及集/场区别见 [公开资料索引](public-sources.md)。

## 统计与导出演示

准备一份你有权处理的 Fountain 稿件。下方路径、N和W都是占位符；运行前替换为稿件路径、集数和总字数目标。需要检查分集预算时，另传入你自己的预算JSON文件。

```text
python scripts/script_metrics.py path/to/your-script.fountain --expected-episodes N --target-words W --tolerance 0.05 --json sample-metrics.json
python scripts/script_metrics.py path/to/your-script.fountain --expected-episodes N --target-words W --episode-budgets path/to/episode-budgets.json --json sample-metrics.json
python scripts/export_screenplay.py path/to/your-script.fountain --output sample.pdf --title "PROJECT TITLE" --episode-page-break
```

统计和导出只能核查正文结构、预算及格式转换，不能证明故事质量、母语效果、法律合规或市场表现。修改后重新统计和渲染，并检查生成文件。