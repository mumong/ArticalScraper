#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试工具 - 检查文章source名称映射
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

async def debug_sources():
    """调试source名称映射"""
    print("🔍 调试source名称映射...")
    
    try:
        # 加载配置
        config = ConfigManager(str(root_dir / "config.yaml"))
        
        # 获取数据库路径
        db_path = str(root_dir / config.get_database_path())
        
        # 创建爬虫实例
        crawler = ContentCrawler(config, db_path)
        
        # 只抓取几篇文章进行调试
        print("\n📋 配置中的数据源:")
        enabled_sources = config.get_enabled_sources()
        for source_id, source_config in enabled_sources.items():
            print(f"  ID: {source_id}")
            print(f"  名称: {source_config['name']}")
            print(f"  URL: {source_config['base_url']}")
            print()
        
        print("\n🕷️  开始抓取（限制数量）...")
        articles = await crawler.crawl_all_sites()
        
        print(f"\n📊 抓取到的文章source统计:")
        source_count = {}
        for article in articles:
            source = article.source
            if source not in source_count:
                source_count[source] = []
            source_count[source].append(article.title)
        
        for source, titles in source_count.items():
            print(f"  Source: '{source}' ({len(titles)} 篇)")
            for title in titles[:3]:  # 只显示前3个标题
                print(f"    - {title[:60]}...")
            if len(titles) > 3:
                print(f"    ... 还有 {len(titles) - 3} 篇")
            print()
        
        print("\n📋 报告分类配置:")
        report_config = config.get_report_config()
        categories = report_config.get('categories', {})
        for cat_name, cat_info in categories.items():
            print(f"  分类: {cat_name}")
            print(f"  期望的sources: {cat_info.get('sources', [])}")
            
            # 检查实际匹配的文章
            matched_articles = 0
            for source in cat_info.get('sources', []):
                if source in source_count:
                    matched_articles += len(source_count[source])
            
            print(f"  实际匹配的文章数: {matched_articles}")
            print()
        
        # 检查具体的不匹配情况
        print("\n❌ 可能的映射问题:")
        all_config_sources = set()
        for cat_info in categories.values():
            all_config_sources.update(cat_info.get('sources', []))
        
        actual_sources = set(source_count.keys())
        
        print(f"  配置中期望的sources: {all_config_sources}")
        print(f"  实际抓取到的sources: {actual_sources}")
        
        missing_in_config = actual_sources - all_config_sources
        missing_in_actual = all_config_sources - actual_sources
        
        if missing_in_config:
            print(f"  ⚠️  实际抓取到但配置中缺失的sources: {missing_in_config}")
        
        if missing_in_actual:
            print(f"  ⚠️  配置中期望但实际未抓取到的sources: {missing_in_actual}")
        
    except Exception as e:
        print(f"❌ 调试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_sources())