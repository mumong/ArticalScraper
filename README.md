# 🚀 技术动态月报生成器

> 自动抓取技术网站内容，AI智能分析生成月度技术报告

## ✨ 核心功能

- 🤖 **AI智能分析**: 深度分析技术文章，提取创新点和价值
- 🌐 **多数据源**: Kubernetes、CNCF、阿里云、华为云等技术网站
- 📊 **结构化报告**: 按分类生成专业的技术动态报告
- 🗓️ **时间段配置**: 支持生成当前月份或历史月份报告
- ⚙️ **高度可配置**: 所有配置通过配置文件管理

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置API密钥

编辑 `config.yaml`，填入你的AI API密钥：

```yaml
ai:
  provider: "deepseek"  # 选择AI提供商
  api_keys:
    deepseek: "your_api_key_here"
```

### 3. 运行生成报告

```bash
python3 src/simple_runner.py
```

## ⚙️ 重要配置说明

### AI配置
```yaml
ai:
  provider: "deepseek"    # AI提供商: deepseek, zhipu
  model: "deepseek-chat"  # 对应模型
  max_tokens: 8000       # 最大token数
```

### 报告时间段配置
```yaml
report:
  # 不配置 specific_month 时：生成当前月份报告（1号到今天）
  # 配置 specific_month 时：生成指定月份完整报告
  specific_month: "2025-07"  # 可选，格式：YYYY-MM
```

### 数据源配置
```yaml
sources:
  kubernetes_blog:
    enabled: true         # 是否启用此数据源
    max_articles: 15      # 最大抓取文章数
```

## 📊 输出结果

运行后会在 `reports/` 目录生成报告文件：
- 文件名格式：`tech_report_YYYY_MM_DD_HHMM.md`
- 包含技术动态概览、创新亮点、技术价值、应用场景等

## 🛠️ 调试工具

```bash
# 快速测试抓取功能
python3 src/debug/quick_test.py

# 测试报告生成（跳过AI分析）
python3 src/debug/debug_report.py

# 测试月份配置功能
python3 src/debug/test_month_config.py

# 调试source名称映射
python3 src/debug/debug_sources.py

# 完整测试流程
python3 src/debug/test_runner.py
```

## 📋 项目结构

```
grapth/
├── config.yaml           # 主配置文件
├── src/                  # 源代码
│   ├── simple_runner.py  # 主运行脚本
│   ├── config_manager.py # 配置管理
│   ├── monthly_tech_crawler.py # 核心功能
│   └── debug/           # 调试工具
│       ├── quick_test.py      # 快速测试
│       ├── debug_report.py    # 报告调试
│       ├── debug_sources.py   # 来源调试
│       ├── test_month_config.py # 月份配置测试
│       └── test_runner.py      # 完整测试
├── reports/              # 生成的报告
├── data/                 # 数据库
└── requirements.txt      # Python依赖
```

## 🐛 常见问题

**1. ModuleNotFoundError**
```bash
# 确保在项目根目录运行
cd grapth
python3 src/simple_runner.py
```

**2. API调用失败**
- 检查 `config.yaml` 中的API密钥是否正确
- 确保网络连接正常

**3. 抓取失败**
- 检查网站是否可访问
- 在配置中禁用有问题的数据源

## 🎯 自定义

### 切换AI提供商
```yaml
ai:
  provider: "zhipu"      # 改为智谱AI
  model: "glm-4.5"       # 对应模型
```

### 添加新数据源
在 `config.yaml` 的 `sources` 部分添加新网站配置

### 修改报告分类
调整 `config.yaml` 中的 `report.categories` 配置

---

**MIT License** - 可自由使用和修改