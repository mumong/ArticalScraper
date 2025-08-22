#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测试修复效果
"""

import asyncio
import sys
from pathlib import Path

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
root_dir = current_dir.parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(current_dir.parent))

from config_manager import ConfigManager
from monthly_tech_crawler import ContentCrawler

async def quick_test():
    """快速测试抓取效果"""
    print("🚀 快速测试修复效果...")
    
    try:
        # 加载配置
        config = ConfigManager(str(root_dir / "config.yaml"))
        
        # 获取数据库路径
        db_path = str(root_dir / config.get_database_path())
        
        # 创建爬虫实例
        crawler = ContentCrawler(config, db_path)
        
        # 只抓取文章，不进行AI分析
        print("\n🕷️  抓取文章...")
        articles = await crawler.crawl_all_sites()
        
        # 统计各来源文章数量
        source_count = {}
        for article in articles:
            source = article.source
            if source not in source_count:
                source_count[source] = []
            source_count[source].append(article)
        
        print(f"\n📊 文章统计:")
        for source, article_list in source_count.items():
            print(f"  {source}: {len(article_list)} 篇")
            # 显示前3篇标题
            for article in article_list[:3]:
                print(f"    - {article.title[:60]}...")
            if len(article_list) > 3:
                print(f"    ... 还有 {len(article_list) - 3} 篇")
            print()
        
        # 检查Kubernetes Blog文章
        if "Kubernetes Blog" in source_count:
            k8s_articles = source_count["Kubernetes Blog"]
            print(f"✅ 成功抓取到 {len(k8s_articles)} 篇Kubernetes Blog文章:")
            for article in k8s_articles:
                print(f"  - {article.title}")
        else:
            print("❌ 未抓取到Kubernetes Blog文章")
        
        # 检查分类映射
        print(f"\n📋 分类映射检查:")
        report_config = config.get_report_config()
        categories = report_config.get('categories', {})
        
        for cat_name, cat_info in categories.items():
            expected_sources = cat_info.get('sources', [])
            total_articles = 0
            
            for source in expected_sources:
                if source in source_count:
                    total_articles += len(source_count[source])
            
            print(f"  {cat_name}: 期望来源 {expected_sources}, 总共 {total_articles} 篇文章")
        
        print(f"\n🎉 修复验证完成!")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(quick_test())