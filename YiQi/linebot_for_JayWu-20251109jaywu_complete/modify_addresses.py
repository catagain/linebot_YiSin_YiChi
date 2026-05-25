import json
import os
import string

def load_existing_addresses():
    """載入現有的地址數據"""
    try:
        with open('available_addresses.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        print("警告: JSON 文件格式錯誤，將創建新文件")
        return []

def save_addresses(addresses):
    """保存地址數據到文件"""
    with open('available_addresses.json', 'w', encoding='utf-8') as f:
        json.dump(addresses, f, ensure_ascii=False, indent=2)
    print(f"成功保存 {len(addresses)} 筆地址資料")

def load_case_names():
    """載入現有的案名數據"""
    try:
        with open('addresses.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        print("警告: addresses.json 文件格式錯誤，將創建新文件")
        return []

def save_case_names(case_names):
    """保存案名數據到文件"""
    with open('addresses.json', 'w', encoding='utf-8') as f:
        json.dump(case_names, f, ensure_ascii=False, indent=2)
    print(f"成功保存 {len(case_names)} 筆案名資料到 addresses.json")

def update_case_name(case_name):
    """更新案名列表，如果案名不存在則添加"""
    case_names = load_case_names()
    if case_name not in case_names:
        case_names.append(case_name)
        save_case_names(case_names)
        print(f"案名「{case_name}」已添加到 addresses.json")
    else:
        print(f"案名「{case_name}」已存在於 addresses.json")
    
    # 同步到資料庫（如果已實現）
    try:
        from db import sync_json_to_db, check_addresses_table
        sync_json_to_db()
        check_addresses_table()
    except ImportError:
        print("提示: db 模組不可用，無法同步到資料庫")

def generate_building_addresses(case_name, floor_range, units, password):
    """生成大樓類型的地址"""
    addresses = []
    start_floor, end_floor = map(int, floor_range.split('-'))
    
    # 轉換戶別數為相應的字母，例如 1=A, 2=B, 3=C...
    unit_letters = string.ascii_uppercase[:units]
    
    for floor in range(start_floor, end_floor + 1):
        for unit in unit_letters:
            address = {
                "address": f"{case_name}_{floor}{unit}",
                "password": password
            }
            addresses.append(address)
    
    return addresses

def generate_house_addresses(case_name, units, password):
    """生成透天類型的地址"""
    addresses = []
    
    for i in range(1, units + 1):
        address = {
            "address": f"{case_name}_{i}A",
            "password": password
        }
        addresses.append(address)
    
    return addresses

def check_duplicate_addresses(existing_addresses, new_addresses):
    """檢查是否有重複的地址"""
    existing_addr_set = {addr["address"] for addr in existing_addresses}
    duplicates = []
    
    for addr in new_addresses:
        if addr["address"] in existing_addr_set:
            duplicates.append(addr["address"])
    
    return duplicates

def main():
    print("=== 批量新增地址資料 ===")
    
    # 載入現有地址數據
    existing_addresses = load_existing_addresses()
    print(f"已載入現有地址數據，共 {len(existing_addresses)} 筆")
    
    # 獲取用戶輸入
    case_name = input("請輸入案名 (如 鷁欣緻境): ")
    
    building_type = ""
    while building_type not in ["1", "2"]:
        building_type = input("請選擇建築類型 (1:大樓 2:透天): ")
    
    # 根據建築類型，生成對應的地址
    new_addresses = []
    if building_type == "1":  # 大樓
        units = int(input("請輸入每層戶別數 (如 4 表示 A,B,C,D): "))
        floor_range = input("請輸入樓層範圍 (如 2-9): ")
        password = input("請輸入預設密碼: ")
        
        new_addresses = generate_building_addresses(case_name, floor_range, units, password)
    else:  # 透天
        units = int(input("請輸入戶別數: "))
        password = input("請輸入預設密碼: ")
        
        new_addresses = generate_house_addresses(case_name, units, password)
    
    # 檢查重複地址
    duplicates = check_duplicate_addresses(existing_addresses, new_addresses)
    if duplicates:
        print(f"警告: 發現 {len(duplicates)} 筆重複地址:")
        for addr in duplicates:
            print(f"- {addr}")
        
        confirm = input("是否仍要繼續新增? (y/n): ")
        if confirm.lower() != 'y':
            print("取消新增操作")
            return
    
    # 預覽新增的地址
    print(f"\n即將新增 {len(new_addresses)} 筆地址:")
    for addr in new_addresses:
        print(f"- {addr['address']} (密碼: {addr['password']})")
    
    confirm = input("\n確認新增這些地址? (y/n): ")
    if confirm.lower() == 'y':
        # 合併並保存地址
        all_addresses = existing_addresses + new_addresses
        save_addresses(all_addresses)
        
        # 更新案名列表
        update_case_name(case_name)
        
        print("地址及案名新增成功!")
    else:
        print("取消新增操作")

if __name__ == "__main__":
    main()