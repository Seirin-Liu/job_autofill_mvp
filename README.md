# 秋招自动填报助手

本项目用于辅助填写秋招/校招网申信息，采用本地化存储，支持浏览器插件快捷填入、自动识别常见表单字段，并可选接入 DeepSeek API。

## 主要功能

- 本地保存个人简历信息
- Web 页面直接编辑个人资料
- 浏览器插件快捷填入本地数据
- 自动填写常见招聘表单字段
- 支持实习、项目、获奖、家庭成员等重复经历逐条添加
- 可选接入 DeepSeek 做字段语义识别
- 不自动提交最终申请，保留人工确认

## 首次运行

1. 双击 `install.bat`  
   首次安装会自动创建 `data/` 和 `data/assets/`。

2. 如需 DeepSeek，编辑 `.env`：

```env
DEEPSEEK_API_KEY=你的Key
```

3. 双击启动：

```text
start.bat
```

4. 浏览器打开：

```text
http://127.0.0.1:8765/
```

可直接编辑并保存个人简历信息。

## 安装浏览器插件

Chrome 打开：

```text
chrome://extensions/
```

Edge 打开：

```text
edge://extensions/
```

开启开发者模式，选择“加载已解压的扩展程序”，加载项目中的：

```text
extension/
```

更新插件代码后，需要在扩展管理页点击一次“重新加载”。

## 使用方式

推荐使用：

```text
本地数据快捷填入
```

先点击招聘网站中的目标输入框，再点击插件面板中的本地数据即可直接写入。

也可以使用：

```text
扫描并自动填写全部
```

自动处理普通字段以及实习、项目、获奖、家庭成员等重复信息。

## 数据存储

个人数据主要保存在：

```text
data/profile_seed.json
data/autofill.db
```

建议不要将真实数据提交到 GitHub。

`.gitignore` 建议包含：

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
*.pyc
data/
```

## 日常使用

```text
start.bat
↓
打开招聘网站
↓
打开浏览器插件
↓
快捷填入 / 自动填写
↓
人工检查
↓
手动提交
```