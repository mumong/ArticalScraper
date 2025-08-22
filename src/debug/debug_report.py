#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试报告生成 - 跳过AI分析，直接生成报告
用于验证Kubernetes Blog文章是否包含在最终报告中
"""

import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
root_dir = current_dir.parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(current_dir.parent))

from config_manager import ConfigManager
from monthly_tech_crawler import ContentCrawler, AIAnalyzer, MonthlyReportGenerator

class MockAIAnalyzer:
    """模拟AI分析器，为所有文章生成标准总结"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
    
    async def analyze_articles(self, articles):
        """为所有文章生成标准总结"""
        print(f"🧠 为 {len(articles)} 篇文章生成标准总结...")
        
        # 按来源分组文章
        articles_by_source = {}
        for article in articles:
            source = article.source
            if source not in articles_by_source:
                articles_by_source[source] = []
            articles_by_source[source].append(article)
        
        # 为每篇文章生成总结
        source_summaries = {}
        for source, source_articles in articles_by_source.items():
            print(f"处理 {source} 的 {len(source_articles)} 篇文章...")
            source_summaries[source] = []
            
            for i, article in enumerate(source_articles, 1):
                # 为所有文章生成标准总结
                article.summary = f"""## 核心内容
{article.title}

这是来自 {source} 的重要技术文章，包含了有价值的技术信息和实践分享。

## 🚀 创新亮点
该文章介绍了创新的技术方案或实践方法，具有很强的实用价值。

## 💡 技术价值
解决了实际的技术问题，为开发者提供了具体的解决方案和最佳实践。

## 🎯 应用场景
适用于相关的技术场景和业务需求，可以帮助开发者提升工作效率。

## 🏷️ 关键词
技术, 实践, 创新, 解决方案

## 📈 行业影响
对相关技术领域的发展有积极的推动作用。"""
                
                source_summaries[source].append(article)
        
        return {
            "articles_by_source": source_summaries,
            "article_count": len(articles),
            "sources": list(set([article.source for article in articles])),
            "date_range": "2025-07-01 到 2025-07-29"
        }

async def test_report_generation():
    """测试报告生成"""
    print("🚀 测试报告生成（包含所有文章）...")
    
    try:
        # 加载配置
        config = ConfigManager(str(root_dir / "config.yaml"))
        
        # 获取数据库路径
        db_path = str(root_dir / config.get_database_path())
        
        # 创建组件实例
        crawler = ContentCrawler(config, db_path)
        analyzer = MockAIAnalyzer(config)
        report_generator = MonthlyReportGenerator(crawler, analyzer)
        
        # 抓取文章
        print("\n🕷️  抓取文章...")
        articles = await crawler.crawl_all_sites()
        
        print(f"\n📊 抓取统计:")
        source_count = {}
        for article in articles:
            source = article.source
            if source not in source_count:
                source_count[source] = 0
            source_count[source] += 1
        
        for source, count in source_count.items():
            print(f"  {source}: {count} 篇")
        
        # 生成报告
        print("\n📝 生成报告...")
        report = await report_generator.generate_monthly_report()
        
        # 保存报告
        timestamp = datetime.now().strftime('%Y_%m_%d_%H%M')
        reports_dir = root_dir / "reports"
        reports_dir.mkdir(exist_ok=True)
        report_file = reports_dir / f"debug_report_{timestamp}.md"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n✅ 报告生成完成!")
        print(f"📄 报告文件: {report_file}")
        print(f"📊 文件大小: {os.path.getsize(report_file)} 字节")
        
        # 检查报告中是否包含Kubernetes Blog
        with open(report_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "Kubernetes Blog" in content:
            print("✅ 报告中包含 'Kubernetes Blog'")
        else:
            print("❌ 报告中不包含 'Kubernetes Blog'")
        
        if "Post-Quantum Cryptography" in content:
            print("✅ 报告中包含 Kubernetes Blog 文章标题")
        else:
            print("❌ 报告中不包含 Kubernetes Blog 文章标题")
        
        # 统计报告中各分类的文章数量
        print("\n📋 报告分类统计:")
        categories = config.get_report_config().get('categories', {})
        for cat_name, cat_info in categories.items():
            # 查找报告中的分类标题
            cat_title = f"{cat_info['icon']} {cat_name}"
            if cat_title in content:
                print(f"  ✅ {cat_name}: 分类存在于报告中")
            else:
                print(f"  ❌ {cat_name}: 分类不存在于报告中")
        
        return str(report_file)
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(test_report_generation())