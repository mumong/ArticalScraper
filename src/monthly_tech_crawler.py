#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
月度技术动态抓取分析系统
自动抓取多个技术网站的内容，使用大模型分析总结
"""

import asyncio
import aiohttp
import json
import re
import feedparser
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
import hashlib
import sqlite3
from pathlib import Path
import os
import glob

# 配置管理器导入
try:
    from config_manager import ConfigManager
except ImportError:
    # 如果无法导入，使用简单的配置加载
    import yaml
    class ConfigManager:
        def __init__(self, config_file="config.yaml"):
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        
        def get(self, key, default=None):
            keys = key.split('.')
            value = self.config
            for k in keys:
                value = value[k]
            return value
        
        def get_database_path(self):
            return self.get('database.path', 'data/tech_articles.db')
        
        def get_crawler_config(self):
            return self.get('crawler', {})
        
        def get_sources_config(self):
            return self.get('sources', {})
        
        def get_enabled_sources(self):
            sources = self.get_sources_config()
            enabled = {}
            for source_id, source_config in sources.items():
                if source_config.get('enabled', True):
                    enabled[source_id] = source_config
            return enabled
        
        def get_report_config(self):
            return self.get('report', {})
        
        def get_prompt(self, prompt_name):
            return self.get(f'prompts.{prompt_name}', '')

@dataclass
class Article:
    """文章数据结构"""
    title: str
    url: str
    content: str
    publish_date: str
    source: str
    summary: str = ""
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []

class ContentCrawler:
    """内容抓取器 - 配置化版本"""
    
    def __init__(self, config_manager: ConfigManager, db_path: str = None):
        self.config_manager = config_manager
        self.db_path = db_path or config_manager.get_database_path()
        
        # 从配置获取爬虫设置
        crawler_config = config_manager.get_crawler_config()
        self.jina_api_base = crawler_config.get('jina_api', 'https://r.jina.ai/')
        self.request_delay = crawler_config.get('request_delay', 1)
        self.timeout = crawler_config.get('timeout', 30)
        self.user_agent = crawler_config.get('user_agent', 'Mozilla/5.0 (compatible; TechCrawler/2.0)')
        
        # 从配置获取网站配置
        self.sites_config = config_manager.get_enabled_sources()
        
        self.setup_database()
        self.cleanup_debug_files()
    
    def setup_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_hash TEXT UNIQUE,
                title TEXT,
                url TEXT,
                content TEXT,
                publish_date TEXT,
                source TEXT,
                summary TEXT,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monthly_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year_month TEXT UNIQUE,
                report_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def cleanup_debug_files(self):
        """清理debug文件"""
        try:
            # 查找所有debug文件
            debug_patterns = [
                "debug_*.html",
                "debug_*.txt", 
                "test_*.py",
                "*_debug.html",
                "debug_page_content.py",
                "test_aliyun_apis.py"
            ]
            
            files_removed = 0
            for pattern in debug_patterns:
                for file_path in glob.glob(pattern):
                    try:
                        # 跳过一些可能重要的文件
                        if "crawler" in file_path.lower() and "test" in file_path.lower():
                            continue
                        
                        os.remove(file_path)
                        files_removed += 1
                        print(f"已清理debug文件: {file_path}")
                    except Exception as e:
                        print(f"清理文件失败 {file_path}: {e}")
            
            if files_removed > 0:
                print(f"✅ 已清理 {files_removed} 个debug文件")
                
        except Exception as e:
            print(f"清理debug文件时出错: {e}")
    
    def get_url_hash(self, url: str) -> str:
        """生成URL哈希"""
        return hashlib.md5(url.encode()).hexdigest()
    
    async def fetch_rss_articles(self, session: aiohttp.ClientSession, rss_url: str, source: str) -> List[Article]:
        """从RSS Feed抓取文章"""
        articles = []
        try:
            print(f"正在抓取RSS: {rss_url}")
            async with session.get(rss_url, timeout=30) as response:
                if response.status == 200:
                    rss_content = await response.text()
                    
                    # 解析RSS
                    feed = feedparser.parse(rss_content)
                    
                    for entry in feed.entries:
                        # 检查文章日期是否在本月
                        published_date = entry.get('published_parsed')
                        if published_date:
                            pub_date = datetime(*published_date[:6])
                            if not self.is_current_month_article(pub_date.strftime('%Y-%m-%d')):
                                continue
                        
                        # 提取文章信息
                        title = entry.get('title', '未知标题')
                        url = entry.get('link', '')
                        content = entry.get('summary', '') or entry.get('description', '')
                        pub_date_str = pub_date.strftime('%Y-%m-%d') if published_date else datetime.now().strftime('%Y-%m-%d')
                        
                        # 清理HTML标签
                        content = re.sub(r'<[^>]+>', '', content)
                        content = content.strip()[:2000]
                        
                        article = Article(
                            title=title,
                            url=url,
                            content=content,
                            publish_date=pub_date_str,
                            source=source
                        )
                        articles.append(article)
                        
                    print(f"从RSS {source} 抓取到 {len(articles)} 篇本月文章")
                else:
                    print(f"RSS抓取失败 {rss_url}: {response.status}")
                    
        except Exception as e:
            print(f"RSS抓取错误 {rss_url}: {e}")
            
        return articles

    async def fetch_with_dynamic_loading(self, url: str, source: str) -> List[Article]:
        """使用动态加载抓取文章（用于SPA页面）"""
        articles = []
        try:
            # 这里可以使用requests_html或selenium
            # 暂时先使用简单的API方式
            print(f"尝试动态抓取 {source}...")
            
            # 针对阿里云和华为云的特殊处理
            if "aliyun" in url.lower():
                # 可以尝试阿里云的API接口
                articles = await self.fetch_aliyun_articles()
            elif "huaweicloud" in url.lower():
                # 可以尝试华为云的API接口
                articles = await self.fetch_huawei_articles()
                
        except Exception as e:
            print(f"动态抓取错误 {source}: {e}")
            
        return articles

    async def fetch_aliyun_articles(self) -> List[Article]:
        """阿里云开发者社区特定抓取"""
        articles = []
        try:
            print("使用优化的阿里云抓取逻辑...")
            
            # 使用有效的阿里云URL
            urls_to_try = [
                "https://developer.aliyun.com/blog/",  # 博客页面，包含文章
                # "https://developer.aliyun.com/",       # 主页，包含大量文章链接
            ]
            
            async with aiohttp.ClientSession() as session:
                article_links = set()
                
                for url in urls_to_try:
                    print(f"正在抓取阿里云URL: {url}")
                    
                    # 获取页面内容
                    content = await self.fetch_with_jina(session, url)
                    if not content:
                        print(f"无法获取页面内容: {url}")
                        continue
                    
                    print(f"成功获取内容，长度: {len(content)} 字符")
                    
                    # 提取文章链接 - 基于实际页面结构优化
                    patterns = [
                        # HTML href属性：href="/article/1673073"
                        r'href="(/article/\d+[^"]*)"',
                        # 完整链接：href="https://developer.aliyun.com/article/1673073"  
                        r'href="(https://developer\.aliyun\.com/article/\d+[^"]*)"',
                        # 直接链接匹配
                        r'(https://developer\.aliyun\.com/article/\d+)',
                        # HTML链接标签
                        r'<a[^>]*href="([^"]*article/\d+[^"]*)"[^>]*>',
                        # JSON格式数据
                        r'"url"\s*:\s*"([^"]*article/\d+[^"]*)"',
                        # 标题链接格式（blog页面特有）
                        r'class="blog-card-title"[^>]*href="(/article/\d+[^"]*)"',
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        for match in matches:
                            link = match
                            if link:
                                # 确保是完整的URL
                                if link.startswith('/'):
                                    link = f"https://developer.aliyun.com{link}"
                                elif not link.startswith('http'):
                                    link = f"https://developer.aliyun.com/article/{link}"
                                
                                # 清理URL中的多余参数
                                link = link.split('#')[0].split('?')[0]
                                article_links.add(link)
                    
                    # 短暂延迟避免请求过快
                    await asyncio.sleep(0.5)
                
                print(f"从阿里云页面提取到 {len(article_links)} 个文章链接")
                
                if not article_links:
                    print("❌ 未能提取到任何文章链接")
                    return articles
                
                # 解析每篇文章 - 限制数量避免过多请求
                max_articles = min(len(article_links), 15)  # 限制最多15篇
                
                for i, link in enumerate(list(article_links)[:max_articles]):
                    try:
                        print(f"正在解析文章 {i+1}/{max_articles}: {link}")
                        article = await self.parse_article(session, link, "阿里云开发者社区")
                        if article:
                            # 检查文章是否为本月发布（放宽检查）
                            if self.is_current_month_article(article.publish_date):
                                articles.append(article)
                                print(f"✅ 成功获取本月文章: {article.title[:50]}...")
                            else:
                                print(f"⏸️  跳过非本月文章: {article.title[:50]}... (日期: {article.publish_date})")
                        
                        # 避免请求过快
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        print(f"解析文章失败 {link}: {e}")
                        continue
                
        except Exception as e:
            print(f"阿里云抓取错误: {e}")
            
        return articles

    async def fetch_huawei_articles(self) -> List[Article]:
        """华为云技术博客特定抓取"""
        articles = []
        try:
            # 这里可以实现华为云特定的抓取逻辑
            print("暂未实现华为云动态抓取，使用传统方式...")
        except Exception as e:
            print(f"华为云抓取错误: {e}")
        return articles

    async def fetch_with_jina(self, session: aiohttp.ClientSession, url: str) -> str:
        """使用Jina Reader抓取内容，失败时使用备用方案"""
        try:
            # 首先尝试Jina Reader
            jina_url = f"{self.jina_api_base}{url}"
            async with session.get(jina_url, timeout=30) as response:
                if response.status == 200:
                    content = await response.text()
                    if content and len(content) > 100:  # 确保内容不为空
                        return content
                    else:
                        print(f"Jina返回内容过少，尝试直接访问: {url}")
                else:
                    print(f"Jina抓取失败 {url}: {response.status}，尝试直接访问")
        except Exception as e:
            print(f"Jina抓取错误 {url}: {e}，尝试直接访问")
        
        # 备用方案：直接访问网站
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    content = await response.text()
                    print(f"直接访问成功: {url}")
                    return content
                else:
                    print(f"直接访问也失败 {url}: {response.status}")
                    return ""
        except Exception as e:
            print(f"直接访问错误 {url}: {e}")
            return ""
    
    async def extract_article_links(self, session: aiohttp.ClientSession, site_config: Dict) -> List[str]:
        """提取文章链接"""
        base_url = site_config["base_url"]
        site_name = site_config["name"]
        
        print(f"正在抓取 {site_name} 的文章链接...")
        content = await self.fetch_with_jina(session, base_url)
        
        if not content:
            print(f"无法获取 {site_name} 的内容")
            return []
        
        # 调试：保存抓取到的原始内容（可选，注释掉以减少输出）
        # debug_file = f"debug_{site_name.replace(' ', '_')}.html"
        # try:
        #     with open(debug_file, 'w', encoding='utf-8') as f:
        #         f.write(content[:5000])  # 只保存前5000字符用于调试
        #     print(f"调试信息已保存到 {debug_file}")
        # except Exception as e:
        #     print(f"保存调试文件失败: {e}")
        
        # 不同网站使用不同的链接提取策略
        links = set()
        
        if "kubernetes.io/blog" in base_url:
            # Kubernetes博客 - 基于实际网页结构优化（markdown列表格式）
            patterns = [
                # 匹配markdown列表中的链接：- [x] [标题](https://kubernetes.io/blog/2025/07/18/pqc-in-k8s/)
                r'- \[x\] \[([^\]]+)\]\((https://kubernetes\.io/blog/\d{4}/\d{2}/\d{2}/[^)]+)\)',
                r'- \[x\] \[([^\]]+)\]\((/blog/\d{4}/\d{2}/\d{2}/[^)]+)\)',
                # 匹配没有markdown的直接链接
                r'\[([^\]]+)\]\((https://kubernetes\.io/blog/\d{4}/\d{2}/\d{2}/[^)]+)\)',
                r'\[([^\]]+)\]\((/blog/\d{4}/\d{2}/\d{2}/[^)]+)\)',
                # HTML格式的备用匹配
                r'href="(https://kubernetes\.io/blog/\d{4}/\d{2}/\d{2}/[^"]+)"',
                r'href="(/blog/\d{4}/\d{2}/\d{2}/[^"]+)"'
            ]
        elif "developer.aliyun.com" in base_url:
            # 阿里云开发者社区 - 基于实际页面结构优化
            patterns = [
                # Markdown格式：[标题](https://developer.aliyun.com/article/1673073 "标题")
                r'\[([^\]]*)\]\((https://developer\.aliyun\.com/article/\d+)[^)]*\)',
                # 直接链接匹配
                r'(https://developer\.aliyun\.com/article/\d+)',
                # HTML href属性
                r'href="(https://developer\.aliyun\.com/article/\d+[^"]*)"',
                # 相对路径：href="/article/1673073"
                r'href="(/article/\d+[^"]*)"',
                # HTML链接标签完整匹配
                r'<a[^>]*href="([^"]*article/\d+[^"]*)"[^>]*>',
                # 标题链接格式
                r'<h[1-6][^>]*><a[^>]*href="([^"]*article/\d+[^"]*)"[^>]*>.*?</a></h[1-6]>',
                # JSON格式数据
                r'"url"\s*:\s*"([^"]*article/\d+[^"]*)"'
            ]
        elif "huaweicloud.com" in base_url:
            # 华为云 - 基于实际网页结构优化
            patterns = [
                # 匹配标准链接：[](https://bbs.huaweicloud.com/blogs/456624)
                r'\[\]\（(https://bbs\.huaweicloud\.com/blogs/\d+)\）',
                r'\[\]\(https://bbs\.huaweicloud\.com/blogs/(\d+)\)',
                # 匹配标题链接：[标题](https://bbs.huaweicloud.com/blogs/456624)
                r'\[([^\]]+)\]\(https://bbs\.huaweicloud\.com/blogs/(\d+)[^)]*\)',
                # 匹配HTML格式的链接
                r'href="(https://bbs\.huaweicloud\.com/blogs/\d+[^"]*)"',
                r'href="(/blogs/\d+[^"]*)"',
                # 备用模式
                r'<a[^>]*href="([^"]*blogs/\d+[^"]*)"[^>]*>',
                r'"url"\s*:\s*"([^"]*blogs/\d+[^"]*)"'
            ]
        elif "cncf.io" in base_url:
            # CNCF - 基于实际网页结构优化
            patterns = [
                # 匹配具体的博客链接格式：/blog/2025/07/23/project-spotlight-kgateway/
                r'href="(/blog/\d{4}/\d{2}/\d{2}/[^"]*)"',
                r'href="(https://www\.cncf\.io/blog/\d{4}/\d{2}/\d{2}/[^"]*)"',
                # 匹配标题链接：[标题](https://www.cncf.io/blog/2025/07/23/project-spotlight-kgateway/)
                r'\[([^\]]+)\]\((https://www\.cncf\.io/blog/\d{4}/\d{2}/\d{2}/[^)]*)\)',
                r'\[([^\]]+)\]\((/blog/\d{4}/\d{2}/\d{2}/[^)]*)\)',
                # 匹配HTML中的链接（这里是关键修复）
                r'<a[^>]*href="(/blog/\d{4}/\d{2}/\d{2}/[^"]*)"[^>]*>',
                r'<a[^>]*href="(https://www\.cncf\.io/blog/\d{4}/\d{2}/\d{2}/[^"]*)"[^>]*>',
                # 更简单的博客链接匹配
                r'href="(/blog/[^"]*)"',
                r'href="(https://www\.cncf\.io/blog/[^"]*)"'
            ]
        elif "lfedge.org" in base_url:
            # LF Edge - 基于实际网页结构匹配
            patterns = [
                # 匹配markdown格式的链接：[EdgeX 4.0 Performance Revealed: Leaner, Smarter and Ready for the Future](https://lfedge.org/edgex-performance-revealed/)
                r'\[([^\]]+)\]\((https://lfedge\.org/[^)]+)\)',
                r'\[([^\]]+)\]\((/[^)]+)\)',
                # 匹配READ MORE链接
                r'\[READ more\]\((https://lfedge\.org/[^)]+)\)',
                r'\[read more\]\((/[^)]+)\)',
                # 匹配HTML格式的链接
                r'href="(https://lfedge\.org/[^"]*)"',
                r'href="(/[^"]*)"',
                # 匹配具体的文章链接，排除导航链接
                r'href="(https://lfedge\.org/[^"]*(?:edgex|akraino|eve|fledge|instantx|infiniedge)[^"]*)"',
                r'href="(/[^"]*(?:edgex|akraino|eve|fledge|instantx|infiniedge)[^"]*)"',
            ]
        else:
            # 通用模式 - 更广泛的匹配
            patterns = [
                r'href="([^"]*(?:blog|article|post)/[^"]*)"',
                r'href="(/[^"]*\d{4}[^"]*)"',
                r'<a[^>]*href="([^"]*)"[^>]*>.*?(?:阅读|查看|详情|Read more|View)',
                r'<h[1-6][^>]*><a[^>]*href="([^"]*)"[^>]*>.*?</a></h[1-6]>'
            ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            # print(f"模式 '{pattern[:50]}...' 匹配到 {len(matches)} 个结果")  # 调试信息，可注释
            for match in matches:
                link = ""
                # 处理不同的匹配结果格式
                if isinstance(match, tuple):
                    # 对于元组，优先选择包含完整URL的部分
                    for part in match:
                        if part and ('http' in part or part.startswith('/')):
                            link = part
                            break
                    # 如果没找到合适的，使用最后一个非空元素
                    if not link:
                        for part in reversed(match):
                            if part:
                                link = part
                                break
                else:
                    link = match
                
                # 确保链接有效且非空
                if link and link.strip():
                    link = link.strip()
                    
                    # 清理链接中的额外内容（如引号中的标题）
                    if ' "' in link:
                        link = link.split(' "')[0]  # 去掉引号后的标题部分
                    if '"' in link:
                        link = link.replace('"', '')  # 去掉所有引号
                    
                    link = link.strip()
                    
                    if link.startswith('http'):
                        links.add(link)
                    elif link.startswith('/'):
                        links.add(urljoin(base_url, link))
                    else:
                        # 对于华为云等数字ID格式，补全路径
                        if "huaweicloud.com" in base_url and link.isdigit():
                            full_link = f"https://bbs.huaweicloud.com/blogs/{link}"
                            links.add(full_link)
                        else:
                            links.add(urljoin(base_url, link))
        
        # 过滤掉无效链接并进行日期过滤
        valid_links = []
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        for link in links:
            # 跳过静态资源和无关文件
            if any(ext in link.lower() for ext in ['.css', '.js', '.png', '.jpg', '.gif', '.svg', '.ico', '.pdf', '.woff', '.zip']):
                continue
            
            # 跳过明显的非内容链接
            if any(pattern in link.lower() for pattern in ['page/', 'category/', 'tag/', 'wp-content', 'projects/', 'fonts/']):
                continue
            
            # 根据不同网站进行日期过滤
            if "kubernetes.io/blog" in base_url or "cncf.io/blog" in base_url:
                # 对于有日期结构的URL，进行日期过滤
                date_match = re.search(r'/blog/(\d{4})/(\d{2})/(\d{2})/', link)
                if date_match:
                    year, month, day = map(int, date_match.groups())
                    # 只保留当前年份当前月份的文章
                    if year == current_year and month == current_month:
                        valid_links.append(link)
                else:
                    # 如果无法提取日期，也保留（作为备用）
                    valid_links.append(link)
            elif "huaweicloud.com" in base_url:
                # 华为云的链接都保留，稍后在parse_article中过滤
                valid_links.append(link)
            elif "lfedge.org" in base_url:
                # LF Edge只保留文章链接，排除导航和其他页面
                if (not any(skip in link.lower() for skip in ['page/', 'category/', 'tag/', 'wp-content', 'projects/', 'members/', 'about/', 'resources/', 'events/', 'news/blog/', 'news/press/', 'wiki']) 
                    and len(link.split('/')) >= 4  # 确保链接有足够的路径深度
                    and not link.endswith('.org/') 
                    and not link.endswith('.org')):
                    valid_links.append(link)
            else:
                # 其他网站的链接直接保留
                valid_links.append(link)
        
        print(f"从 {site_name} 提取到 {len(valid_links)} 个链接")
        
        # 对CNCF增加限制，它的文章特别多
        if "cncf.io" in base_url:
            return valid_links[:20]  # CNCF限制20个
        else:
            return valid_links[:15]  # 其他网站限制15个
    
    async def parse_article(self, session: aiohttp.ClientSession, url: str, source: str) -> Optional[Article]:
        """解析单篇文章"""
        content = await self.fetch_with_jina(session, url)
        if not content:
            return None
        
        # 提取标题
        title_patterns = [
            r'<title>([^<]+)</title>',
            r'<h1[^>]*>([^<]+)</h1>',
            r'title:\s*"([^"]+)"',
            r'title:\s*([^\n]+)'
        ]
        
        title = "未知标题"
        for pattern in title_patterns:
            title_match = re.search(pattern, content, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()
                # 清理标题中的HTML实体和多余字符
                title = re.sub(r'&[^;]+;', '', title)
                title = re.sub(r'\s+', ' ', title).strip()
                break
        
        # 提取发布日期 - 支持多种格式，阿里云优化
        date_patterns = [
            # 阿里云日期格式：2025-07-24（优先匹配）
            r'(\d{4}-\d{2}-\d{2})',
            # 华为云格式：2025/07/18
            r'(\d{4}/\d{2}/\d{2})',
            # CNCF格式：July 23, 2025
            r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})',
            # 阿里云中文格式：2025年07月24日
            r'(\d{4}年\d{2}月\d{2}日)',
            # 其他常见格式
            r'(\d{2}/\d{2}/\d{4})',
            r'Published on ([^<\n]+)',
            r'Date: ([^<\n]+)',
            r'发布时间[：:]\s*([^\n<]+)',
            r'时间[：:]\s*([^\n<]+)',
            # 阿里云特有的日期格式
            r'(\d{4}-\d{1,2}-\d{1,2})',
            # 阿里云可能的ISO格式
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})'
        ]
        
        publish_date = ""
        for pattern in date_patterns:
            date_match = re.search(pattern, content)
            if date_match:
                date_str = date_match.group(1).strip()
                # 转换为标准格式
                publish_date = self.normalize_date(date_str)
                if publish_date:
                    break
        
        if not publish_date:
            publish_date = datetime.now().strftime("%Y-%m-%d")
        
        # 清理内容
        clean_content = re.sub(r'<[^>]+>', '', content)
        clean_content = re.sub(r'\s+', ' ', clean_content).strip()
        
        return Article(
            title=title,
            url=url,
            content=clean_content[:3000],  # 增加内容长度
            publish_date=publish_date,
            source=source
        )
    
    def normalize_date(self, date_str: str) -> str:
        """将各种日期格式转换为标准格式 YYYY-MM-DD"""
        try:
            date_formats = [
                '%Y-%m-%d',
                '%Y/%m/%d', 
                '%m/%d/%Y',
                '%d/%m/%Y',
                '%Y-%m-%dT%H:%M:%S',
                '%B %d, %Y',  # July 23, 2025
                '%b %d, %Y'   # Jul 23, 2025
            ]
            
            # 处理中文日期格式：2025年07月24日
            chinese_date_match = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_str)
            if chinese_date_match:
                year, month, day = chinese_date_match.groups()
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            for fmt in date_formats:
                try:
                    parsed_date = datetime.strptime(date_str, fmt)
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    continue
            
            # 如果无法解析，返回空字符串
            return ""
            
        except Exception:
            return ""
    
    async def crawl_github_issues(self, session: aiohttp.ClientSession) -> List[Article]:
        """抓取GitHub Issues"""
        articles = []
        try:
            # 获取本月1号到今天的issues
            current_date = datetime.now()
            first_day_of_month = current_date.replace(day=1)
            since_date = first_day_of_month.isoformat()
            
            api_url = f"https://api.github.com/repos/kubernetes/enhancements/issues?since={since_date}&state=all&per_page=50"
            print(f"抓取GitHub Issues: {first_day_of_month.strftime('%Y-%m-%d')} 到 {current_date.strftime('%Y-%m-%d')}")
            
            async with session.get(api_url) as response:
                if response.status == 200:
                    issues = await response.json()
                    
                    for issue in issues:
                        # 检查issue的创建时间或更新时间是否在本月
                        created_date = datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00')).replace(tzinfo=None)
                        updated_date = datetime.fromisoformat(issue['updated_at'].replace('Z', '+00:00')).replace(tzinfo=None)
                        
                        # 只要创建时间或更新时间在本月就包含
                        if (created_date >= first_day_of_month or updated_date >= first_day_of_month):
                            article = Article(
                                title=issue['title'],
                                url=issue['html_url'],
                                content=issue.get('body', '')[:2000],
                                publish_date=issue['created_at'][:10],
                                source="Kubernetes Enhancements"
                            )
                            articles.append(article)
                else:
                    print(f"GitHub API调用失败: {response.status}")
        
        except Exception as e:
            print(f"GitHub抓取错误: {e}")
        
        print(f"从GitHub抓取到 {len(articles)} 个issues")
        return articles
    
    def is_current_month_article(self, publish_date: str) -> bool:
        """检查文章是否在报告时间段内（向后兼容方法）"""
        # 使用配置管理器获取报告时间段
        try:
            report_config = self.config_manager.get_report_config()
            specific_month = report_config.get('specific_month')
            
            if specific_month:
                # 解析配置的月份
                year, month = map(int, specific_month.split('-'))
                
                # 计算月份第一天
                start_date = datetime(year, month, 1)
                
                # 计算月份最后一天
                if month == 12:
                    next_month = datetime(year + 1, 1, 1)
                else:
                    next_month = datetime(year, month + 1, 1)
                
                end_date = next_month - timedelta(days=1)
                
                # 如果是当前月份，使用今天作为结束日期
                current_date = datetime.now()
                if year == current_date.year and month == current_date.month:
                    end_date = current_date
            else:
                # 默认使用当前月份
                current_date = datetime.now()
                start_date = current_date.replace(day=1)
                end_date = current_date
            
            if not publish_date:
                return True  # 如果没有日期，假设在报告期内
            
            # 尝试解析不同格式的日期
            date_formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%Y-%m-%dT%H:%M:%S']
            article_date = None
            
            for fmt in date_formats:
                try:
                    article_date = datetime.strptime(publish_date[:19], fmt)
                    break
                except ValueError:
                    continue
            
            if not article_date:
                return True  # 无法解析日期时假设在报告期内
                
            # 检查是否在报告时间范围内
            return (start_date <= article_date <= end_date)
            
        except Exception as e:
            print(f"检查文章日期失败: {e}")
            return True  # 出错时假设在报告期内
    
    def save_article(self, article: Article):
        """保存文章到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        url_hash = self.get_url_hash(article.url)
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO articles 
                (url_hash, title, url, content, publish_date, source, summary, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                url_hash, article.title, article.url, article.content,
                article.publish_date, article.source, article.summary,
                json.dumps(article.tags)
            ))
            conn.commit()
        except Exception as e:
            print(f"保存文章错误: {e}")
        finally:
            conn.close()
    
    async def crawl_all_sites(self) -> List[Article]:
        """抓取所有网站 - 优先使用RSS"""
        all_articles = []
        
        async with aiohttp.ClientSession() as session:
            # 抓取GitHub Issues
            github_articles = await self.crawl_github_issues(session)
            all_articles.extend(github_articles)
            
            # 抓取其他网站
            for site_key, site_config in self.sites_config.items():
                if site_key == "kubernetes_enhancements":
                    continue  # 已经处理过了
                
                print(f"\n正在抓取: {site_config['name']}")
                
                try:
                    site_articles = []
                    
                    # 优先尝试RSS
                    if 'rss_feed' in site_config:
                        print(f"使用RSS抓取 {site_config['name']}...")
                        site_articles = await self.fetch_rss_articles(
                            session, 
                            site_config['rss_feed'], 
                            site_config['name']
                        )
                    
                    # 如果RSS失败或没有RSS，尝试动态抓取
                    if not site_articles and site_config.get('dynamic_loading'):
                        print(f"尝试动态抓取 {site_config['name']}...")
                        site_articles = await self.fetch_with_dynamic_loading(
                            site_config['base_url'], 
                            site_config['name']
                        )
                    
                    # 如果以上都失败，使用传统抓取方式
                    if not site_articles:
                        print(f"使用传统方式抓取 {site_config['name']}...")
                        article_links = await self.extract_article_links(session, site_config)
                        
                        # 解析每篇文章
                        for link in article_links[:10]:  # 限制数量避免过多请求
                            article = await self.parse_article(session, link, site_config['name'])
                            if article and self.is_current_month_article(article.publish_date):
                                site_articles.append(article)
                            
                            # 避免请求过快
                            await asyncio.sleep(1)
                    
                    # 保存文章
                    for article in site_articles:
                        self.save_article(article)
                        all_articles.append(article)
                    
                    print(f"从 {site_config['name']} 总共获取到 {len(site_articles)} 篇文章")
                
                except Exception as e:
                    print(f"抓取网站错误 {site_config['name']}: {e}")
        
        return all_articles

class AIAnalyzer:
    """AI分析器 - 配置化版本"""
    
    def __init__(self, config_manager: ConfigManager, api_key: str, api_base: str = None, model: str = None):
        self.config_manager = config_manager
        self.api_key = api_key
        self.api_base = api_base or "https://api.deepseek.com/v1"
        self.model = model or "deepseek-chat"
        
        # 从配置获取AI设置
        ai_config = config_manager.get_ai_config() if hasattr(config_manager, 'get_ai_config') else {}
        self.max_tokens = ai_config.get('max_tokens', 8000)
        self.temperature = ai_config.get('temperature', 0.7)
        
        # 从配置获取提示词模板
        self.summary_prompt = config_manager.get_prompt('summary')
        if not self.summary_prompt:
            # 如果配置中没有，使用默认提示词
            self.summary_prompt = """你是一个专业的技术分析师，专门分析云原生、开源项目和开发者生态的技术动态。请深度分析以下网站内容，提供结构化的总结。

分析以下网站内容并按格式输出：

## 核心内容
<用2-3个要点总结主要技术内容>

## 🚀 创新亮点
<如果有创新性技术、突破性功能或首创性内容，请重点分析其创新之处>

## 💡 技术价值
<分析这个技术/项目/更新解决了什么问题，带来什么价值和好处>

## 🎯 应用场景
<说明适用的场景、用户群体或使用cases>

## 🏷️ 关键词
<提取3-5个关键技术标签，如：Kubernetes, AI, 安全, 性能优化等>

## 📈 行业影响
<分析对行业、开发者或企业的潜在影响>

严格要求：
- 优先识别和突出任何创新性、突破性或独特的技术内容
- 重点分析技术的实际价值和意义，不只是功能描述
- 如果是版本更新，要说明改进的意义和带来的好处
- 使用专业但易懂的语言
- 保持简洁但信息丰富
- 必须使用中文

网站内容：
%s"""
    
    async def summarize_single_article(self, article: Article) -> str:
        """使用自定义prompt总结单篇文章"""
        try:
            # 使用自定义prompt格式化内容
            prompt_content = self.summary_prompt % article.content
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                data = {
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": prompt_content}
                    ],
                    "max_tokens": 500,
                    "temperature": 0.7
                }
                
                async with session.post(f"{self.api_base}/chat/completions", 
                                      headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result['choices'][0]['message']['content']
                    else:
                        print(f"API调用失败: {response.status}")
                        return f"无法总结文章: {article.title}"
        except Exception as e:
            print(f"总结文章错误: {e}")
            return f"总结失败: {article.title}"

    async def analyze_articles(self, articles: List[Article]) -> Dict:
        """分析文章内容"""
        # 按来源分组文章
        articles_by_source = {}
        for article in articles:
            source = article.source
            if source not in articles_by_source:
                articles_by_source[source] = []
            articles_by_source[source].append(article)
        
        # 为每篇文章生成总结
        print("正在为每篇文章生成AI总结...")
        source_summaries = {}
        
        for source, source_articles in articles_by_source.items():
            print(f"处理 {source} 的文章...")
            source_summaries[source] = []
            
            # 根据文章数量动态调整处理数量，确保重要来源不被遗漏
            base_max = 15 # 基础最大数量
            if len(source_articles) <= 10:
                # 如果文章数量较少，全部处理
                max_articles = len(source_articles)
            elif len(source_articles) > 50:
                # 如果文章很多，适当增加处理数量
                max_articles = min(len(source_articles), 20)
            else:
                max_articles = min(len(source_articles), base_max)
            
            for i, article in enumerate(source_articles[:max_articles], 1):
                print(f"  处理文章 {i}/{max_articles}: {article.title[:50]}...")
                article.summary = await self.summarize_single_article(article)
                source_summaries[source].append(article)
                await asyncio.sleep(0.5)  # 减少延迟，加快处理速度
        
        return {
            "articles_by_source": source_summaries,
            "article_count": len(articles),
            "sources": list(set([article.source for article in articles])),
            "date_range": self.get_date_range(articles)
        }
    
    def get_date_range(self, articles: List[Article]) -> str:
        """获取报告配置的日期范围"""
        # 使用配置管理器获取报告时间段
        try:
            report_config = self.config_manager.get_report_config()
            specific_month = report_config.get('specific_month')
            
            if specific_month:
                # 解析配置的月份
                year, month = map(int, specific_month.split('-'))
                
                # 计算月份第一天
                start_date = datetime(year, month, 1)
                
                # 计算月份最后一天
                if month == 12:
                    next_month = datetime(year + 1, 1, 1)
                else:
                    next_month = datetime(year, month + 1, 1)
                
                end_date = next_month - timedelta(days=1)
                
                # 如果是当前月份，使用今天作为结束日期
                current_date = datetime.now()
                if year == current_date.year and month == current_date.month:
                    end_date = current_date
            else:
                # 默认使用当前月份
                current_date = datetime.now()
                start_date = current_date.replace(day=1)
                end_date = current_date
            
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            return f"{start_date_str} 到 {end_date_str}"
            
        except Exception as e:
            print(f"获取报告时间范围失败: {e}")
            # 回退到基于文章日期的范围
            dates = [article.publish_date for article in articles if article.publish_date]
            if not dates:
                return "未知时间范围"
            return f"{min(dates)} 到 {max(dates)}"

class MonthlyReportGenerator:
    """月报生成器 - 配置化版本"""
    
    def __init__(self, crawler: ContentCrawler, analyzer: AIAnalyzer):
        self.crawler = crawler
        self.analyzer = analyzer
        self.config_manager = crawler.config_manager
        
        # 从配置获取报告分类
        self.tech_categories = self.config_manager.get_report_config().get('categories', {})
        
        # 获取报告时间段配置
        self.report_month = self.get_report_month()
        self.report_start_date, self.report_end_date = self.get_report_date_range()
    
    def get_report_month(self) -> str:
        """获取报告月份，格式：YYYY-MM"""
        report_config = self.config_manager.get_report_config()
        specific_month = report_config.get('specific_month')
        
        if specific_month:
            return specific_month
        else:
            # 默认使用当前月份
            return datetime.now().strftime("%Y-%m")
    
    def get_report_date_range(self) -> tuple:
        """获取报告时间范围 (start_date, end_date)"""
        try:
            # 解析月份
            year, month = map(int, self.report_month.split('-'))
            
            # 计算月份第一天
            start_date = datetime(year, month, 1)
            
            # 计算月份最后一天
            if month == 12:
                next_month = datetime(year + 1, 1, 1)
            else:
                next_month = datetime(year, month + 1, 1)
            
            end_date = next_month - timedelta(days=1)
            
            # 如果是当前月份，使用今天作为结束日期
            current_date = datetime.now()
            if year == current_date.year and month == current_date.month:
                end_date = current_date
            
            return start_date, end_date
            
        except Exception as e:
            print(f"解析报告月份失败: {e}")
            # 使用当前月份作为默认
            current_date = datetime.now()
            start_date = current_date.replace(day=1)
            return start_date, current_date
    
    def is_in_report_period(self, publish_date: str) -> bool:
        """检查文章是否在报告时间段内"""
        try:
            if not publish_date:
                return True  # 如果没有日期，假设在报告期内
            
            # 尝试解析不同格式的日期
            date_formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%Y-%m-%dT%H:%M:%S']
            article_date = None
            
            for fmt in date_formats:
                try:
                    article_date = datetime.strptime(publish_date[:19], fmt)
                    break
                except ValueError:
                    continue
            
            if not article_date:
                return True  # 无法解析日期时假设在报告期内
                
            # 检查是否在报告时间范围内
            return (self.report_start_date <= article_date <= self.report_end_date)
            
        except Exception as e:
            print(f"检查文章日期失败: {e}")
            return True  # 出错时假设在报告期内
    
    async def generate_monthly_report(self) -> str:
        """生成月度报告"""
        print("开始抓取文章...")
        articles = await self.crawler.crawl_all_sites()
        
        print(f"共抓取到 {len(articles)} 篇文章")
        
        if not articles:
            return "本月暂无新文章"
        
        print("开始AI分析...")
        analysis = await self.analyzer.analyze_articles(articles)
        
        # 生成按来源分组的报告
        current_date = datetime.now()
        start_date_str = self.report_start_date.strftime('%Y-%m-%d')
        end_date_str = self.report_end_date.strftime('%Y-%m-%d')
        
        report = f"""# 🚀 技术动态月度跟进报告

**📅 生成时间**: {current_date.strftime('%Y-%m-%d %H:%M:%S')}  
**📊 统计周期**: {start_date_str} ～ {end_date_str}  
**📝 文章数量**: {analysis['article_count']} 篇  
**🏷️ 信息来源**: {', '.join(analysis['sources'])}

---

## 📋 本月技术动态概览

"""
        
        # 从配置获取技术分类
        tech_categories = self.tech_categories
        
        # 按技术分类生成内容
        for category_name, category_info in tech_categories.items():
            category_articles = []
            
            # 收集该分类下的所有文章
            for source in category_info.get("sources", []):
                if source in analysis['articles_by_source']:
                    category_articles.extend(analysis['articles_by_source'][source])
            
            if not category_articles:
                continue
                
            report += f"""## {category_info['icon']} {category_name}

> 📖 {category_info['description']}

"""
            
            # 限制显示数量，优先显示有创新亮点的文章
            # 如果文章很多，增加显示数量以确保包含重要来源
            if len(category_articles) > 30:
                display_count = min(len(category_articles), 25)  # 文章很多时显示25篇
            else:
                display_count = min(len(category_articles), 20)  # 其他情况显示20篇
            
            # 排序：有创新亮点的文章优先，同时确保来源多样性
            def sort_by_innovation_and_source(article):
                if article.summary:
                    parsed = self.parse_structured_summary(article.summary)
                    # 有创新亮点的文章优先
                    innovation_score = 0 if parsed.get('innovation') else 1
                    # 在同一分类中，尽量让不同来源的文章都有展示机会
                    # 给予较少文章来源的一些优先级
                    source_priority = hash(article.source) % 10  # 基于source名称的简单哈希
                    return (innovation_score, source_priority)
                return (1, hash(article.source) % 10)
            
            category_articles.sort(key=sort_by_innovation_and_source)
            
            for i, article in enumerate(category_articles[:display_count], 1):
                if article.summary:
                    parsed_info = self.parse_structured_summary(article.summary)
                    
                    # 更突出的标题格式
                    report += f"## {i}. 📄 {article.title}\n\n"
                    
                    # 创新亮点优先且更加突出
                    if parsed_info.get('innovation'):
                        report += f"### 🚀 创新亮点\n"
                        report += f"**{parsed_info['innovation']}**\n\n"
                    
                    # 核心内容
                    if parsed_info.get('core_content'):
                        report += f"### 💡 核心内容\n"
                        report += f"{parsed_info['core_content']}\n\n"
                    
                    # 技术价值
                    if parsed_info.get('tech_value'):
                        report += f"#### 🎯 技术价值\n"
                        report += f"{parsed_info['tech_value']}\n\n"
                    
                    # 应用场景
                    if parsed_info.get('use_cases'):
                        report += f"#### 🔧 应用场景\n"
                        report += f"{parsed_info['use_cases']}\n\n"
                    
                    # 关键词标签 - 使用标签样式
                    if parsed_info.get('keywords'):
                        keywords_list = [kw.strip() for kw in parsed_info['keywords'].replace('，', ',').split(',') if kw.strip()]
                        keywords_formatted = ' '.join([f"`{kw}`" for kw in keywords_list])
                        report += f"#### 🏷️ 技术标签\n"
                        report += f"{keywords_formatted}\n\n"
                    
                    # 文章信息
                    report += f"#### 📋 文章信息\n"
                    report += f"- **📅 发布时间**: {article.publish_date}\n"
                    report += f"- **🔗 原文链接**: [查看详情]({article.url})\n"
                    report += f"- **📤 来源平台**: {article.source}\n\n"
                    
                    report += "---\n\n"
            
            # 如果有更多文章，显示统计信息
            if len(category_articles) > display_count:
                report += f"> 📊 **统计信息**: 该分类本月共发布 **{len(category_articles)}** 篇文章，上方展示前 **{display_count}** 篇重点内容\n\n"
        
        # 保存报告
        self.save_monthly_report(report)
        
        return report
    
    def parse_structured_summary(self, summary: str) -> dict:
        """解析结构化的AI分析结果"""
        parsed = {}
        
        try:
            # 提取各个部分的内容
            sections = {
                'core_content': r'## 核心内容\s*\n(.*?)(?=##|\Z)',
                'innovation': r'## 🚀 创新亮点\s*\n(.*?)(?=##|\Z)',
                'tech_value': r'## 💡 技术价值\s*\n(.*?)(?=##|\Z)',
                'use_cases': r'## 🎯 应用场景\s*\n(.*?)(?=##|\Z)',
                'keywords': r'## 🏷️ 关键词\s*\n(.*?)(?=##|\Z)',
                'industry_impact': r'## 📈 行业影响\s*\n(.*?)(?=##|\Z)'
            }
            
            for key, pattern in sections.items():
                match = re.search(pattern, summary, re.DOTALL | re.MULTILINE)
                if match:
                    content = match.group(1).strip()
                    # 清理内容，去除HTML标签和多余的换行
                    content = re.sub(r'<[^>]+>', '', content)
                    content = re.sub(r'\n+', ' ', content)
                    content = content.strip()
                    
                    # 如果内容不为空且不是占位符
                    if content and content not in ['无', '暂无', '不适用', '<无>']:
                        parsed[key] = content[:200] + ('...' if len(content) > 200 else '')
            
            # 如果没有解析到结构化内容，回退到简单提取
            if not parsed:
                # 尝试提取Key Takeaways格式（兼容旧格式）
                if "Key Takeaways" in summary:
                    parts = summary.split("Key Takeaways")
                    if len(parts) > 1:
                        content = parts[1].strip()
                        parsed['core_content'] = content[:200] + "..."
                else:
                    # 直接使用前200个字符作为核心内容
                    parsed['core_content'] = summary[:200] + "..."
                    
        except Exception as e:
            print(f"解析结构化总结时出错: {e}")
            # 回退到简单模式
            parsed['core_content'] = summary[:200] + "..."
        
        return parsed
    
    def extract_key_points(self, summary: str) -> str:
        """从总结中提取关键要点（备用方法）"""
        # 这个方法现在主要作为备用
        parsed = self.parse_structured_summary(summary)
        return parsed.get('core_content', summary[:150] + "...")
    
    def extract_innovation(self, summary: str) -> str:
        """提取创新性内容（备用方法）"""
        parsed = self.parse_structured_summary(summary)
        return parsed.get('innovation', '')
    
    def save_monthly_report(self, report: str):
        """保存月度报告"""
        conn = sqlite3.connect(self.crawler.db_path)
        cursor = conn.cursor()
        
        year_month = datetime.now().strftime('%Y-%m')
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO monthly_reports (year_month, report_content)
                VALUES (?, ?)
            ''', (year_month, report))
            conn.commit()
            
            # 同时保存到文件，确保使用UTF-8编码
            reports_dir = Path("reports")
            reports_dir.mkdir(exist_ok=True)
            report_filename = reports_dir / f"tech_report_{datetime.now().strftime('%Y_%m_%d_%H%M')}.md"
            with open(report_filename, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"📝 报告已保存到文件: {report_filename}")
            
        except Exception as e:
            print(f"保存报告错误: {e}")
        finally:
            conn.close()

# 使用示例
async def main():
    """主函数 - 配置化版本"""
    # 初始化配置管理器
    config_manager = ConfigManager("config.yaml")
    
    # 从配置获取AI设置
    ai_config = config_manager.get_ai_config()
    provider = ai_config.get('provider', 'deepseek')
    model = ai_config.get('model', 'deepseek-chat')
    
    # 获取API密钥和URL
    api_keys = ai_config.get('api_keys', {})
    api_urls = ai_config.get('api_urls', {})
    
    api_key = api_keys.get(provider, '')
    api_base = api_urls.get(provider, 'https://api.deepseek.com/v1')
    
    # 初始化组件
    crawler = ContentCrawler(config_manager)
    analyzer = AIAnalyzer(config_manager, api_key, api_base, model)
    report_generator = MonthlyReportGenerator(crawler, analyzer)
    
    # 生成月度报告
    report = await report_generator.generate_monthly_report()
    
    # 保存到文件
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    report_file = reports_dir / f"monthly_report_{datetime.now().strftime('%Y_%m')}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"月度报告已生成: {report_file}")
    print("\n" + "="*50)
    print(report)

if __name__ == "__main__":
    asyncio.run(main())