# Adaptive Study Center · 分步备考学习中心

把自己的讲义和题目做成离线 HTML 学习中心。先诊断，再一次问一步；学生出错时定位第一处错误，最后用变式题检验能否独立作答。填空题和大题分开练习，保留草稿、收藏和错题记录。

## 两种安装方式

- **Codex**：克隆仓库，将含 `SKILL.md` 的仓库根目录安装为个人 skills 目录下的 `adaptive-study-center`。在新任务中附上资料，输入：`使用 $adaptive-study-center，根据这些讲义和题目生成可离线使用的完整 HTML。`
- **WorkBuddy**：下载 [WorkBuddy 技能包](https://github.com/741-xiao/adaptive-study-center/raw/refs/heads/main/dist/adaptive-study-center-workbuddy.zip)，在「技能 → 添加技能 → 上传技能」中选择 ZIP。两个版本使用同一个 Skill 标识和源码。

## 运行示例

下载并双击 [公开示例 HTML](assets/计算机网络_完整学习中心.html)，不需要服务器。源码位于 `assets/source/`，原创样题位于 `examples/chapters/`。示例展示数据和流程，不代表任何教材的完整题库。在线登录和服务端授权是可选功能，详见 [账号说明](assets/source/账号版使用说明.md)。

在仓库根目录运行：

```sh
python scripts/inspect_bundle.py examples/chapters
cd assets/source
node tools/import-bank.mjs ../../examples/chapters
node tools/build-complete.mjs
```

最后一步在当前目录生成完整 HTML。发布时将其复制到 `assets/`，再在仓库根目录运行 `python scripts/package_workbuddy.py` 更新导入包。

## 许可与数据

本仓库的代码、文档和自编示例采用 [MIT License](LICENSE)。不分发原课件、私人题库、学生记录或登录凭据；使用本工具处理的外部资料仍遵循各自的授权。
