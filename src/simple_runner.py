#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版技术动态月报生成器
直接运行即可生成月度报告 - 配置化版本
"""

import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path

# 添加当前目录到Python路径，确保能导入模块
current_dir = Path(__file__).parent
root_dir = current_dir.parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(root_dir))

# 导入配置管理器和核心模块
from config_manager import ConfigManager
from monthly_tech_crawler import ContentCrawler, AIAnalyzer, MonthlyReportGenerator

class SimpleReportRunner:
    """简化的报告运行器 - 配置化版本"""
    
    def __init__(self):
        # 加载配置
        self.config = ConfigManager(str(root_dir / "config.yaml"))
        
        # 从配置获取AI设置
        ai_config = self.config.get_ai_config()
        self.provider = ai_config.get('provider', 'deepseek')
        self.model = ai_config.get('model', 'deepseek-chat')
        
        # 获取API密钥和URL
        api_keys = ai_config.get('api_keys', {})
        api_urls = ai_config.get('api_urls', {})
        
        self.api_key = api_keys.get(self.provider, '')
        self.api_base = api_urls.get(self.provider, 'https://api.deepseek.com/v1')
        
        # 获取其他配置
        self.max_tokens = ai_config.get('max_tokens', 8000)
        self.temperature = ai_config.get('temperature', 0.7)
        
        print("🚀 技术动态月报生成器")
        print("=" * 50)
        print(f"AI提供商: {self.provider}")
        print(f"AI模型: {self.model}")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
    
    async def run(self):
        """运行主流程"""
        try:
            # 初始化组件 - 传入配置
            print("\n📊 初始化系统组件...")
            
            # 获取数据库路径
            db_path = str(root_dir / self.config.get_database_path())
            
            # 创建组件实例，传入配置
            crawler = ContentCrawler(self.config, db_path)
            analyzer = AIAnalyzer(self.config, self.api_key, self.api_base, self.model)
            report_generator = MonthlyReportGenerator(crawler, analyzer)
            
            # 生成报告
            print("\n📝 开始生成月度报告...")
            report = await report_generator.generate_monthly_report()
            
            # 保存文件到reports目录
            timestamp = datetime.now().strftime('%Y_%m_%d_%H%M')
            reports_dir = root_dir / "reports"
            reports_dir.mkdir(exist_ok=True)
            report_file = reports_dir / f"tech_report_{timestamp}.md"
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"\n✅ 报告生成完成!")
            print(f"📄 文件保存为: {report_file}")
            print(f"📊 文件大小: {os.path.getsize(report_file)} 字节")
            
            # 显示报告预览
            print("\n" + "="*60)
            print("📋 报告预览:")
            print("="*60)
            
            # 只显示前1000个字符
            preview = report[:1000]
            if len(report) > 1000:
                preview += "\n\n... (内容较长，请查看完整文件)"
            
            print(preview)
            
            return str(report_file)
            
        except Exception as e:
            print(f"\n❌ 生成报告时出错: {e}")
            import traceback
            traceback.print_exc()
            return None

def main():
    """主函数"""
    print("开始运行技术动态爬虫...")
    
    runner = SimpleReportRunner()
    
    try:
        # 运行异步任务
        result = asyncio.run(runner.run())
        
        if result:
            print(f"\n🎉 成功! 报告已保存到: {result}")
        else:
            print("\n💥 报告生成失败")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  用户中断操作")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 运行出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()