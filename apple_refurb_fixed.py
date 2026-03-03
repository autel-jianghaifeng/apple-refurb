#!/usr/bin/env python3
"""
Apple 官翻 Mac 价格监控程序
从页面内嵌的 REFURB_GRID_BOOTSTRAP JSON 数据中提取商品信息，只需一次请求。
"""

import requests
import pandas as pd
from datetime import datetime
import re
import json
import time


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


def extract_bootstrap_data(html_content):
    """从 HTML 中提取 REFURB_GRID_BOOTSTRAP JSON 数据"""
    match = re.search(r'window\.REFURB_GRID_BOOTSTRAP\s*=\s*(\{.+?\});\s*</script>', html_content, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}")
        return None


def parse_products(data):
    """从 REFURB_GRID_BOOTSTRAP 数据中解析商品列表"""
    tiles = data.get('tiles', [])
    dimensions = data.get('dictionaries', {}).get('dimensions', {})

    def lookup(dimension_name, key):
        """从字典中查找显示文本"""
        if not key:
            return ''
        dim = dimensions.get(dimension_name, {})
        entry = dim.get(key, {})
        text = entry.get('text', key) if isinstance(entry, dict) else key
        return re.sub(r'[\s\-]+(?=英寸)', '', text)

    products = []
    for tile in tiles:
        dims = tile.get('filters', {}).get('dimensions', {})
        price_info = tile.get('price', {}).get('currentPrice', {})
        raw_amount = price_info.get('raw_amount', '0')

        try:
            price = int(float(raw_amount))
        except (ValueError, TypeError):
            continue

        title = tile.get('title', '')

        # 从标题提取芯片信息
        chip = ''
        chip_match = re.search(r'Apple (M\d+(?:\s+(?:Pro|Max|Ultra))?)', title)
        if chip_match:
            chip = chip_match.group(1)

        # 从标题提取 CPU/GPU 核心数
        cpu_cores = ''
        cpu_match = re.search(r'(\d+)\s*核中央处理器', title)
        if cpu_match:
            cpu_cores = cpu_match.group(1) + '核'

        gpu_cores = ''
        gpu_match = re.search(r'(\d+)\s*核图形处理器', title)
        if gpu_match:
            gpu_cores = gpu_match.group(1) + '核'

        # 从 dimensions 字典查找结构化数据
        model_key = dims.get('refurbClearModel', '')
        screen_key = dims.get('dimensionScreensize', '')
        color_key = dims.get('dimensionColor', '')
        memory_key = dims.get('tsMemorySize', '')
        storage_key = dims.get('dimensionCapacity', '')
        year_key = dims.get('dimensionRelYear', '')

        url = tile.get('productDetailsUrl', '').split('?')[0]
        if url and not url.startswith('http'):
            url = 'https://www.apple.com.cn' + url

        products.append({
            'model': lookup('refurbClearModel', model_key),
            'screen_size': lookup('dimensionScreensize', screen_key),
            'chip': chip,
            'cpu_cores': cpu_cores,
            'gpu_cores': gpu_cores,
            'color': lookup('dimensionColor', color_key),
            'memory': lookup('tsMemorySize', memory_key),
            'storage': lookup('dimensionCapacity', storage_key),
            'release_year': year_key,
            'price': price,
            'title': title,
            'url': url,
        })

    return products


def save_results(df):
    """保存结果到 CSV"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_file = f'./data_{timestamp}.csv'
    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
    print(f"已保存到 CSV: {csv_file}")
    return csv_file


def main():
    """主函数"""
    print("=" * 80)
    print("Apple 官翻 Mac 价格监控程序")
    print("=" * 80)

    url = 'https://www.apple.com.cn/shop/refurbished/mac'

    print(f"\n正在获取页面: {url}")
    html_content = fetch_page(url)

    if not html_content:
        print("无法获取页面内容")
        return

    print("正在解析内嵌数据...")
    data = extract_bootstrap_data(html_content)

    if not data:
        print("未找到 REFURB_GRID_BOOTSTRAP 数据")
        return

    products = parse_products(data)
    print(f"找到 {len(products)} 个商品")

    if not products:
        print("未找到任何商品信息")
        return

    df = pd.DataFrame(products)

    # 排序
    df.sort_values(
        by=['price', 'memory', 'storage', 'cpu_cores', 'gpu_cores', 'chip', 'title'],
        inplace=True,
    )
    df.reset_index(drop=True, inplace=True)

    # 打印预览
    print("\n" + "=" * 120)
    print("商品信息预览（前 20 条）:")
    print("=" * 120)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 150)
    pd.set_option('display.max_colwidth', 40)
    display_cols = ['model', 'screen_size', 'chip', 'memory', 'storage', 'price']
    print(df[display_cols].head(20).to_string(index=True))
    print("=" * 120)

    # 保存结果
    print("\n正在保存结果...")
    csv_file = save_results(df)

    # 打印统计信息
    print("\n" + "=" * 80)
    print("统计信息:")
    print("=" * 80)
    print(f"总商品数: {len(df)}")
    print(f"价格范围: RMB {df['price'].min():,} - RMB {df['price'].max():,}")
    print(f"平均价格: RMB {df['price'].mean():.0f}")

    if df['model'].notna().any() and (df['model'] != '').any():
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

    return csv_file


if __name__ == '__main__':
    main()
