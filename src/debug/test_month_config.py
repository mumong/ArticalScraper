#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试报告时间段配置功能
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
root_dir = current_dir.parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(current_dir.parent))

from config_manager import ConfigManager
from monthly_tech_crawler import ContentCrawler, AIAnalyzer, MonthlyReportGenerator

async def test_month_config():
    """测试月份配置功能"""
    print("🧪 测试报告时间段配置功能...")
    
    try:
        # 测试默认配置（当前月份）
        print("\n📋 测试1: 默认配置（当前月份）")
        config = ConfigManager(str(root_dir / "config.yaml"))
        
        # 获取数据库路径
        db_path = str(root_dir / config.get_database_path())
        
        # 创建组件实例
        crawler = ContentCrawler(config, db_path)
        
        # 测试时间段获取
        report_config = config.get_report_config()
        specific_month = report_config.get('specific_month')
        
        print(f"  配置的specific_month: {specific_month}")
        
        # 模拟一些测试文章
        from monthly_tech_crawler import Article
        test_articles = [
            Article(
                title="测试文章1",
                url="https://example.com/1",
                content="测试内容1",
                publish_date="2025-07-15",
                source="测试来源",
                summary="",
                tags=""
            ),
            Article(
                title="测试文章2", 
                url="https://example.com/2",
                content="测试内容2",
                publish_date="2025-06-15",
                source="测试来源",
                summary="",
                tags=""
            )
        ]
        
        # 测试文章过滤
        print(f"  测试文章总数: {len(test_articles)}")
        filtered_articles = [article for article in test_articles if crawler.is_current_month_article(article.publish_date)]
        print(f"  过滤后文章数: {len(filtered_articles)}")
        
        for article in filtered_articles:
            print(f"    - {article.title} ({article.publish_date})")
        
        # 测试配置指定月份
        print("\n📋 测试2: 配置指定月份")
        
        # 临时修改配置
        config.config['report']['specific_month'] = '2025-06'
        
        # 重新创建爬虫实例
        crawler2 = ContentCrawler(config, db_path)
        
        filtered_articles2 = [article for article in test_articles if crawler2.is_current_month_article(article.publish_date)]
        print(f"  配置月份为2025-06时，过滤后文章数: {len(filtered_articles2)}")
        
        for article in filtered_articles2:
            print(f"    - {article.title} ({article.publish_date})")
        
        # 测试报告生成器
        print("\n📋 测试3: 报告生成器时间段")
        
        # 创建模拟分析器
        class MockAnalyzer:
            async def analyze_articles(self, articles):
                return {
                    "articles_by_source": {"测试来源": articles},
                    "article_count": len(articles),
                    "sources": ["测试来源"],
                    "date_range": "2025-07-01 到 2025-07-30"
                }
        
        analyzer = MockAnalyzer()
        report_generator = MonthlyReportGenerator(crawler, analyzer)
        
        print(f"  报告月份: {report_generator.report_month}")
        print(f"  报告开始日期: {report_generator.report_start_date.strftime('%Y-%m-%d')}")
        print(f"  报告结束日期: {report_generator.report_end_date.strftime('%Y-%m-%d')}")
        
        # 测试时间段检查
        test_date = "2025-07-15"
        is_in_period = report_generator.is_in_report_period(test_date)
        print(f"  测试日期 {test_date} 是否在报告期内: {is_in_period}")
        
        test_date2 = "2025-06-15"
        is_in_period2 = report_generator.is_in_report_period(test_date2)
        print(f"  测试日期 {test_date2} 是否在报告期内: {is_in_period2}")
        
        print("\n✅ 所有测试完成!")
        
        # 恢复配置
        config.config['report']['specific_month'] = None
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_month_config())