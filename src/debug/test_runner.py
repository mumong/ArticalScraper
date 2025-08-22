#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试抓取流程 - 跳过AI分析
用于快速验证抓取功能是否正常
"""

import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path

# 添加当前目录到Python路径，确保能导入模块
current_dir = Path(__file__).parent
root_dir = current_dir.parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(current_dir.parent))

# 导入配置管理器和核心模块
from config_manager import ConfigManager
from monthly_tech_crawler import ContentCrawler, AIAnalyzer, MonthlyReportGenerator

class TestAIAnalyzer:
    """测试用AI分析器 - 跳过真实AI调用"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
    
    async def analyze_articles(self, articles):
        """模拟AI分析，直接返回基本信息"""
        print(f"🧠 模拟AI分析 {len(articles)} 篇文章...")
        
        # 按来源分组文章
        articles_by_source = {}
        for article in articles:
            source = article.source
            if source not in articles_by_source:
                articles_by_source[source] = []
            articles_by_source[source].append(article)
        
        # 为每篇文章生成模拟总结
        source_summaries = {}
        for source, source_articles in articles_by_source.items():
            print(f"处理 {source} 的文章...")
            source_summaries[source] = []
            
            for i, article in enumerate(source_articles[:10], 1):  # 只处理前10篇
                print(f"  处理文章 {i}/{len(source_articles[:10])}: {article.title[:50]}...")
                
                # 创建模拟总结
                article.summary = f"""## 核心内容
{article.title[:100]}...

## 🚀 创新亮点
这是一个模拟的AI分析结果，用于测试抓取流程。

## 💡 技术价值
该文章提供了有价值的技术信息。

## 🎯 应用场景
适用于技术学习和实践。

## 🏷️ 关键词
技术, 云原生, 实践

## 📈 行业影响
对行业发展有积极影响。"""
                
                source_summaries[source].append(article)
        
        return {
            "articles_by_source": source_summaries,
            "article_count": len(articles),
            "sources": list(set([article.source for article in articles])),
            "date_range": "2025-07-01 到 2025-07-29"
        }

async def test_crawling():
    """测试抓取流程"""
    print("🚀 开始测试抓取流程...")
    
    try:
        # 加载配置
        config = ConfigManager(str(root_dir / "config.yaml"))
        
        # 获取数据库路径
        db_path = str(root_dir / config.get_database_path())
        
        # 创建组件实例
        crawler = ContentCrawler(config, db_path)
        analyzer = TestAIAnalyzer(config)
        report_generator = MonthlyReportGenerator(crawler, analyzer)
        
        # 测试抓取
        print("\n🕷️  开始抓取文章...")
        articles = await crawler.crawl_all_sites()
        
        print(f"\n📊 抓取结果:")
        print(f"总共抓取到 {len(articles)} 篇文章")
        
        # 按来源统计
        articles_by_source = {}
        for article in articles:
            source = article.source
            if source not in articles_by_source:
                articles_by_source[source] = []
            articles_by_source[source].append(article)
        
        print("\n📋 各来源文章统计:")
        for source, source_articles in articles_by_source.items():
            print(f"  {source}: {len(source_articles)} 篇")
        
        # 测试报告生成（跳过AI分析）
        print("\n📝 测试报告生成...")
        report = await report_generator.generate_monthly_report()
        
        # 保存测试报告
        timestamp = datetime.now().strftime('%Y_%m_%d_%H%M')
        reports_dir = root_dir / "reports"
        reports_dir.mkdir(exist_ok=True)
        report_file = reports_dir / f"test_report_{timestamp}.md"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n✅ 测试完成!")
        print(f"📄 测试报告保存为: {report_file}")
        print(f"📊 文件大小: {os.path.getsize(report_file)} 字节")
        
        return str(report_file)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """主函数"""
    print("开始测试抓取流程...")
    
    try:
        # 运行异步任务
        result = asyncio.run(test_crawling())
        
        if result:
            print(f"\n🎉 测试成功! 报告已保存到: {result}")
        else:
            print("\n💥 测试失败")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  用户中断操作")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 运行出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()