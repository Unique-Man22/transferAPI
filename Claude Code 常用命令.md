# Claude Code 常用命令

## 基础命令

### `/help`
显示帮助信息，列出所有可用的命令和功能。

### `/clear`
清除当前对话历史，重新开始新的对话。

### `/fast`
切换到快速模式，使用 Claude Opus 4.6 获得更快的输出速度。

### `/exit`
退出 Claude Code。

### `/powerup`
快速交互学习使用

## 任务管理

### `/tasks`
显示当前会话中的所有任务列表，包括任务状态、描述和进度。

### `/remember <内容>`
让 Claude 记住某些信息，这些信息会被保存到项目的 memory 目录中，供未来会话使用。

### `/forget <内容>`
让 Claude 忘记之前记住的某些信息。

## 计划模式

### `/plan`
进入计划模式，用于在实现复杂功能前先设计实现方案，获得用户批准后再执行。

### `/exit-plan`
退出计划模式，提交计划供用户审批。

## 循环任务

### `/loop <间隔> <命令>`
设置循环任务，按指定间隔重复执行某个命令。
- 示例：`/loop 5m /babysit-prs` - 每 5 分钟检查一次 PR
- 默认间隔为 10 分钟

### `/stop-loop`
停止当前运行的循环任务。

## 技能命令

### `/init`
初始化新的 CLAUDE.md 文件，用于记录代码库文档。

### `/review`
审查当前的 Pull Request。

### `/security-review`
对当前分支的待定更改进行安全审查。

### `/simplify`
审查更改的代码，检查可重用性、质量和效率，然后修复发现的问题。

### `/fewer-permission-prompts`
扫描对话记录中的常见只读 Bash 和 MCP 工具调用，然后添加优先级允许列表到项目的 .claude/settings.json，以减少权限提示。

### `/update-config`
通过 settings.json 配置 Claude Code。用于设置权限、环境变量、钩子等。

### `/keybindings-help`
自定义键盘快捷键、重新绑定按键、添加和弦绑定或修改 ~/.claude/keybindings.json。

## 其他

### `/config`
查看或修改配置设置（如主题、模型等）。

### `/version`
显示 Claude Code 的版本信息。
