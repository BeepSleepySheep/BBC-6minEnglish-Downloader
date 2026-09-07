# BBC 6 Minute English 下载器

一个 Python 命令行工具，用于浏览并批量下载 **BBC Learning English – 6 Minute English**广播节目的Audio，Transcript以及Worksheet，每期节目存放在一个独立文件夹中。

## 功能特性

- 聚合年份归档页（近年）与早年老节目归档页，统一去重生成完整节目列表（500+ 期）。
- 通过解析每期节目页面获取真实下载地址（Audio / Transcript / Worksheet）
- 交互式复选框 **TUI** 选择界面：
  - 方向键移动、`Space` 勾选、`Enter` 确认、`Q` 取消
  - 支持「全选当前页」与「全选全部页面」快捷项
  - `←/→` 翻页，`PgUp/PgDn` 跳转首页/末页
  - 在非交互式终端下自动降级为纯文本序号输入模式
- 每期节目行显示**期数编号**（即 `YYMMDD` 形式的播出日期），避免与列表序号混淆。
- 检索范围可自选：近年按年份逐项勾选，2021 年及之前合并为「老节目」单一选项。
- 一期节目的三个文件（音频/文稿/PDF）全部下载到同一独立文件夹。
- 启动前网络连通性预检，容忍下载站根路径 404。
- 支持断点续传与失败重试，内置 `rich` 进度条。

## 环境要求

- Python 3.8+
- `requests`、`beautifulsoup4`
- `rich`

## 安装

```bash
git clone https://github.com/BeepSleepySheep/BBC-6minEnglish-Downloader.git
cd BBC-6minEnglish-Downloader
pip install -r requirements.txt
```

## 使用方法

```bash
python bbc_6minute_english_downloader.py [命令行参数]
```

### 命令行参数

| 参数 | 说明 |
| --- | --- |
| `--check` | 仅执行网络连通性检测后退出 |
| `--year` | 只检索指定的年份或年份范围，如 `2024`、`2019-2024`、`2015,2018,2020-2022`；不指定时交互式勾选年份范围（回车则为全量） |
| `--out` | 下载保存根目录（不指定时交互询问，回车默认 `~/Downloads/6MinuteEnglish`） |
| `--page-size` | 选择界面每页显示的节目数（默认 20） |
| `--limit` | 只处理最新的 N 期（试跑调试用，0 表示全部） |

### 使用示例

```bash
# 交互式完整运行（先勾选年份范围，再勾选节目）
python bbc_6minute_english_downloader.py

# 仅检测网络连通性
python bbc_6minute_english_downloader.py --check

# 只下载指定年份 / 年份范围到自定义目录
python bbc_6minute_english_downloader.py --year 2026 --out ~/Downloads/BBC6min
python bbc_6minute_english_downloader.py --year 2019-2024 --out ~/Downloads/BBC6min
```

下载内容按每期一个独立文件夹存放，例如：

```
Downloads/6MinuteEnglish/260903/
├── 260903.pdf
├── 260903_download.mp3
└── 260903_transcript.pdf
```

## 关于期数日期

每期 BBC 6 Minute English 节目都有一个 `YYMMDD` 形式的 6 位播出日期编号（如 `260903` → `2026-09-03`）。选择界面直接显示该编号并据此计算日期，无需额外抓取。


## Vibecoding声明

本项目通过 **Vibecoding** 的方式构建，主观目的是在我学习英语的过程中，方便我获取纯正的英语学习资料。实际使用体验都围绕我的个人学习需求展开，因此在功能取舍上以实用为主。

## 免责声明

本工具仅用于索引并下载 **BBC Learning English** 公开发布的多媒体内容，仅供**个人、非商业、学习**用途。本项目与 BBC 无任何隶属或背书关系。请尊重 BBC 的版权与使用条款，请勿将下载内容用于商业转发或再分发。

## 开源许可

[MIT](LICENSE)
