#!/usr/bin/env python3
"""
Apple 官翻 Mac 价格监控程序 - 修正版
从详情页提取准确的价格和配置信息
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def fetch_page(url, retry=3):
    """获取页面内容"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }
    
    for attempt in range(retry):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            if attempt == retry - 1:
                print(f"获取页面失败 {url}: {e}")
                return None
            time.sleep(1)
    return None


def parse_product_list(html_content):
    """从列表页解析商品基本信息和URL"""
    soup = BeautifulSoup(html_content, 'html.parser')
    products = []
    
    # 提取商品详情页链接
    product_links = soup.find_all('a', href=re.compile(r'/shop/product/\w+/a'))
    
    seen_urls = set()
    for link in product_links:
        title = link.get_text(strip=True)
        if title.startswith('翻新'):
            url = link.get('href')
            if not url.startswith('http'):
                url = 'https://www.apple.com.cn' + url
            # 清理 URL 参数
            url = url.split('?')[0]
            
            # 去重
            if url not in seen_urls:
                seen_urls.add(url)
                products.append({
                    'title': title,
                    'url': url
                })
    
    return products


def fetch_product_details(product):
    """获取商品详情页的完整信息，包括准确的价格"""
    url = product.get('url', '')
    if not url:
        return None
    
    try:
        html = fetch_page(url, retry=2)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()
        
        # 提取价格 - 从详情页提取
        price_match = re.search(r'或\s*RMB\s*([\d,]+)', text)
        if not price_match:
            # 尝试其他价格模式
            price_match = re.search(r'RMB\s*([\d,]+)', text)
        
        if price_match:
            price_str = price_match.group(1).replace(',', '')
            try:
                product['price'] = int(price_str)
            except ValueError:
                print(f"价格解析失败: {price_str}")
                return None
        else:
            print(f"未找到价格: {url}")
            return None
        
        # 提取内存信息
        memory_match = re.search(r'(\d+)\s*GB\s*统一内存', text)
        if memory_match:
            product['memory'] = memory_match.group(1) + 'GB'
        else:
            product['memory'] = ''
        
        # 提取存储信息
        storage_match = re.search(r'(\d+)\s*(GB|TB)\s*固态硬盘', text)
        if storage_match:
            product['storage'] = storage_match.group(1) + storage_match.group(2)
        else:
            product['storage'] = ''
        
        # 提取发布年份
        year_match = re.search(r'最初发布于\s*(\d{4})\s*年', text)
        if year_match:
            product['release_year'] = year_match.group(1)
        else:
            product['release_year'] = ''
        
        time.sleep(0.5)  # 避免请求过快
        return product
        
    except Exception as e:
        print(f"获取详情失败 {url}: {e}")
        return None


def extract_basic_details(title):
    """从标题中提取基本产品信息"""
    details = {
        'model': '',
        'screen_size': '',
        'chip': '',
        'cpu_cores': '',
        'gpu_cores': '',
        'color': ''
    }
    
    # 提取机型
    if 'MacBook Air' in title:
        details['model'] = 'MacBook Air'
    elif 'MacBook Pro' in title:
        details['model'] = 'MacBook Pro'
    elif 'Mac mini' in title:
        details['model'] = 'Mac mini'
    elif 'Mac Studio' in title:
        details['model'] = 'Mac Studio'
    elif 'Mac Pro' in title:
        details['model'] = 'Mac Pro'
    elif 'iMac' in title:
        details['model'] = 'iMac'
    elif '显示屏' in title or 'Display' in title:
        details['model'] = '显示屏'
    
    # 提取屏幕尺寸
    screen_match = re.search(r'(\d+(?:\.\d+)?)\s*英寸', title)
    if screen_match:
        details['screen_size'] = screen_match.group(1) + '英寸'
    
    # 提取芯片型号
    chip_match = re.search(r'Apple (M\d+(?:\s+(?:Pro|Max|Ultra))?)', title)
    if chip_match:
        details['chip'] = chip_match.group(1)
    
    # 提取 CPU 核心数
    cpu_match = re.search(r'(\d+)\s*核中央处理器', title)
    if cpu_match:
        details['cpu_cores'] = cpu_match.group(1) + '核'
    
    # 提取 GPU 核心数
    gpu_match = re.search(r'(\d+)\s*核图形处理器', title)
    if gpu_match:
        details['gpu_cores'] = gpu_match.group(1) + '核'
    
    # 提取颜色
    colors = ['深空灰色', '深空黑色', '银色', '星光色', '午夜色', '天蓝色', '金色', '玫瑰金色']
    for color in colors:
        if color in title:
            details['color'] = color
            break
    
    return details


def process_products_parallel(products, max_workers=10):
    """并行处理商品详情获取"""
    print(f"\n正在获取 {len(products)} 个商品的详细信息（包括准确价格）...")
    print("这可能需要几分钟时间，请耐心等待...")
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_product_details, product): product for product in products}
        
        completed = 0
        for future in as_completed(futures):
            completed += 1
            if completed % 10 == 0:
                print(f"进度: {completed}/{len(products)}")
            try:
                result = future.result()
                if result:  # 只保留成功获取的商品
                    results.append(result)
            except Exception as e:
                print(f"处理商品时出错: {e}")
    
    print(f"完成! 成功获取 {len(results)}/{len(products)} 个商品")
    return results


def create_dataframe(products):
    """创建 DataFrame 并整理信息"""
    if not products:
        return pd.DataFrame()
    
    # 为每个产品提取基本信息
    for product in products:
        basic_details = extract_basic_details(product['title'])
        # 只更新不存在的字段
        for key, value in basic_details.items():
            if key not in product or not product.get(key):
                product[key] = value
    
    # 创建 DataFrame
    df = pd.DataFrame(products)
    
    # 确保所有列都存在
    required_columns = ['model', 'screen_size', 'chip', 'cpu_cores', 'gpu_cores', 
                       'color', 'memory', 'storage', 'release_year', 'price', 'title', 'url']
    
    for col in required_columns:
        if col not in df.columns:
            df[col] = ''
    
    # 重新排列列顺序
    columns_order = ['model', 'screen_size', 'chip', 'cpu_cores', 'gpu_cores', 
                     'color', 'memory', 'storage', 'release_year', 'price', 'title', 'url']
    
    df = df[columns_order]
    
    # 按价格排序
    df = df.sort_values('price')
    df = df.reset_index(drop=True)
    
    return df


def save_results(df):
    """保存结果到文件"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 保存为 CSV
    csv_file = f'./apple_refurb_correct_{timestamp}.csv'
    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
    print(f"已保存到 CSV: {csv_file}")
    
    # 保存为 Excel
    excel_file = f'./apple_refurb_correct_{timestamp}.xlsx'
    # df.to_excel(excel_file, index=False, engine='openpyxl')
    # print(f"已保存到 Excel: {excel_file}")
    
    # 保存为 Markdown 表格
    md_file = f'./apple_refurb_correct_{timestamp}.md'
    # with open(md_file, 'w', encoding='utf-8') as f:
    #     f.write('# Apple 官翻 Mac 完整价格表（修正版）\n\n')
    #     f.write(f'**更新时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')
    #     f.write(f'**数据来源**: https://www.apple.com.cn/shop/refurbished/mac\n\n')
    #     f.write('**说明**: 所有价格均从商品详情页直接提取，确保准确性\n\n')
    #     f.write('---\n\n')
        
    #     # 创建显示用的 DataFrame（不包含 URL）
    #     df_display = df.drop(columns=['url'])
    #     f.write(df_display.to_markdown(index=False))
        
    #     f.write('\n\n---\n\n')
    #     f.write('## 统计信息\n\n')
    #     f.write(f'- **总计**: {len(df)} 个商品\n')
    #     f.write(f'- **价格范围**: RMB {df["price"].min():,} - RMB {df["price"].max():,}\n')
    #     f.write(f'- **平均价格**: RMB {df["price"].mean():.0f}\n\n')
        
    #     if 'model' in df.columns and df['model'].notna().any():
    #         f.write('### 按机型统计\n\n')
    #         model_counts = df[df['model'] != '']['model'].value_counts()
    #         for model, count in model_counts.items():
    #             model_df = df[df['model'] == model]
    #             avg_price = model_df['price'].mean()
    #             min_price = model_df['price'].min()
    #             max_price = model_df['price'].max()
    #             f.write(f'- **{model}**: {count} 个 | 价格: RMB {min_price:,} - {max_price:,} | 平均: RMB {avg_price:,.0f}\n')
    
    # print(f"已保存到 Markdown: {md_file}")
    
    return csv_file, excel_file, md_file


def main():
    """主函数"""
    print("=" * 80)
    print("Apple 官翻 Mac 价格监控程序 - 修正版")
    print("=" * 80)
    
    url = 'https://www.apple.com.cn/shop/refurbished/mac'
    
    print(f"\n正在获取商品列表: {url}")
    html_content = fetch_page(url)
    
    if not html_content:
        print("无法获取页面内容")
        return
    
    print("正在解析商品列表...")
    products = parse_product_list(html_content)
    
    print(f"找到 {len(products)} 个商品")
    
    if not products:
        print("未找到任何商品信息")
        return
    
    # 并行获取详细信息（包括准确价格）
    products = process_products_parallel(products, max_workers=10)
    
    if not products:
        print("未能成功获取任何商品详情")
        return
    
    print("\n正在创建数据表格...")
    df = create_dataframe(products)
    
    # 打印预览
    print("\n" + "=" * 120)
    print("商品信息预览（前 20 条）:")
    print("=" * 120)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 150)
    pd.set_option('display.max_colwidth', 40)
    
    # 只显示主要列
    display_cols = ['model', 'screen_size', 'chip', 'memory', 'storage', 'price']
    print(df[display_cols].head(20).to_string(index=True))
    print("=" * 120)
    
    # 保存结果
    print("\n正在保存结果...")
    csv_file, excel_file, md_file = save_results(df)
    
    # 打印统计信息
    print("\n" + "=" * 80)
    print("统计信息:")
    print("=" * 80)
    print(f"总商品数: {len(df)}")
    print(f"价格范围: RMB {df['price'].min():,} - RMB {df['price'].max():,}")
    print(f"平均价格: RMB {df['price'].mean():.0f}")
    
    # 统计有配置信息的商品数
    memory_count = df[df['memory'] != ''].shape[0]
    storage_count = df[df['storage'] != ''].shape[0]
    print(f"\n配置信息完整度:")
    print(f"  包含内存信息: {memory_count}/{len(df)} ({memory_count/len(df)*100:.1f}%)")
    print(f"  包含存储信息: {storage_count}/{len(df)} ({storage_count/len(df)*100:.1f}%)")
    
    if 'model' in df.columns and df['model'].notna().any():
        print(f"\n按机型统计:")
        model_counts = df[df['model'] != '']['model'].value_counts()
        for model, count in model_counts.items():
            model_df = df[df['model'] == model]
            avg_price = model_df['price'].mean()
            min_price = model_df['price'].min()
            max_price = model_df['price'].max()
            print(f"  {model:15s}: {count:2d} 个  |  RMB {min_price:,} - {max_price:,}  |  平均: RMB {avg_price:,.0f}")
    
    print("=" * 80)
    print("\n完成!")
    
    return csv_file, excel_file, md_file


if __name__ == '__main__':
    main()
