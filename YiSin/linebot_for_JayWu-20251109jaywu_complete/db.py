import os
import pymysql
from dotenv import load_dotenv
import json
import random
import string
import logging

# 設置基本日誌配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

def get_connection():
    try:
        conn = pymysql.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            db=os.getenv("DB_NAME"),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        logging.info("資料庫連線成功")
        return conn
    except pymysql.MySQLError as e:
        logging.error(f"資料庫連線失敗: {e}")
        raise Exception(f"資料庫連線失敗: {e}")

def user_exists(line_user_id):
    conn = get_connection()
    with conn:
        with conn.cursor() as cursor:
            sql = "SELECT * FROM users_yisin WHERE line_user_id = %s"
            cursor.execute(sql, (line_user_id,))
            return cursor.fetchone() is not None

def add_user(line_user_id):
    conn = get_connection()
    with conn:
        with conn.cursor() as cursor:
            # 先查詢最大的 id 值
            cursor.execute("SELECT MAX(id) as max_id FROM users_yisin")
            result = cursor.fetchone()
            next_id = 1 if result['max_id'] is None else result['max_id'] + 1
            
            # 插入新用戶時指定 id
            sql = "INSERT INTO users_yisin (id, line_user_id) VALUES (%s, %s)"
            cursor.execute(sql, (next_id, line_user_id))
            conn.commit()
def update_identity(line_user_id, identity):
    conn = get_connection()
    with conn:
        with conn.cursor() as cursor:
            sql = """
            UPDATE users_yisin
            SET identity = %s
            WHERE line_user_id = %s
            """
            cursor.execute(sql, (identity, line_user_id))
            conn.commit()

def get_user(line_user_id):
    conn = get_connection()
    with conn:
        with conn.cursor() as cursor:
            sql = "SELECT * FROM users_yisin WHERE line_user_id = %s"
            cursor.execute(sql, (line_user_id,))
            user = cursor.fetchone()
            if user:
                # 將戶別字串分割成清單，使用 .get() 方法避免 KeyError
                address = user.get('address')
                if address:
                    user['addresses'] = address.split('/')
                else:
                    user['addresses'] = []
            return user

def update_user_step(line_user_id, step):
    conn = get_connection()
    with conn:
        with conn.cursor() as cursor:
            sql = "UPDATE users_yisin SET step = %s WHERE line_user_id = %s"
            cursor.execute(sql, (step, line_user_id))
            conn.commit()

def update_user_field(line_user_id, field_name, value):
    conn = get_connection()
    with conn:
        with conn.cursor() as cursor:
            sql = f"UPDATE users_yisin SET {field_name} = %s WHERE line_user_id = %s"
            cursor.execute(sql, (value, line_user_id))
            conn.commit()

def update_user_mode(line_user_id, mode):
    conn = get_connection()
    with conn:
        with conn.cursor() as cursor:
            sql = "UPDATE users_yisin SET mode = %s WHERE line_user_id = %s"
            cursor.execute(sql, (mode, line_user_id))
            conn.commit()

def clear_user_mode(line_user_id):
    update_user_mode(line_user_id, None)

def update_temp_value(line_user_id, value):
    conn = get_connection()
    with conn:
        with conn.cursor() as cursor:
            sql = "UPDATE users_yisin SET temp_value = %s WHERE line_user_id = %s"
            cursor.execute(sql, (value, line_user_id))
            conn.commit()

def clear_temp_value(line_user_id):
    update_temp_value(line_user_id, None)

def append_address(line_user_id, new_address):
    conn = get_connection()
    with conn:
        with conn.cursor() as cursor:
            # 取得現有的戶別字串
            sql = "SELECT address FROM users_yisin WHERE line_user_id = %s"
            cursor.execute(sql, (line_user_id,))
            result = cursor.fetchone()
            current_address = result['address'] if result and result['address'] else ""

            # 合併戶別
            if current_address:
                updated_address = f"{current_address}/{new_address}"
            else:
                updated_address = new_address
            
            # 更新資料庫
            sql = "UPDATE users_yisin SET address = %s WHERE line_user_id = %s"
            cursor.execute(sql, (updated_address, line_user_id))
            conn.commit()

def add_column_if_not_exists(column_name, column_type):
    """檢查並添加指定的欄位到 users 表"""
    conn = get_connection()
    with conn:
        with conn.cursor() as cursor:
            try:
                # 檢查欄位是否已存在
                sql = """
                SELECT COUNT(*) as count
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'users_yisin' AND COLUMN_NAME = %s
                """
                cursor.execute(sql, (os.getenv("DB_NAME"), column_name))
                result = cursor.fetchone()
                if result and result['count'] == 0:
                    # 欄位不存在，添加欄位
                    sql = f"""
                    ALTER TABLE users_yisin
                    ADD COLUMN {column_name} {column_type}
                    """
                    cursor.execute(sql)
                    conn.commit()
                    logging.info(f"已成功添加 {column_name} 欄位")
                    return True
                else:
                    logging.info(f"{column_name} 欄位已存在")
                    return False
            except pymysql.MySQLError as e:
                logging.error(f"添加 {column_name} 欄位失敗: {e}")
                return False

def ensure_all_required_columns():
    """確保所有必要的欄位都存在於數據庫中"""
    # 定義所有需要的欄位及其類型
    required_columns = {
        'identity': 'VARCHAR(50)',
        'step': 'VARCHAR(100)',
        'mode': 'VARCHAR(100)',
        'temp_value': 'TEXT',
        'address': 'TEXT',
        'name': 'VARCHAR(100)',
        'birthday': 'VARCHAR(20)',
        'phone': 'VARCHAR(20)',
        'email': 'VARCHAR(100)',
        'id_number': 'VARCHAR(20)',
        'is_identified': 'BOOLEAN DEFAULT FALSE'
    }
    
    # 檢查並添加每一個欄位
    added_columns = []
    for column_name, column_type in required_columns.items():
        if add_column_if_not_exists(column_name, column_type):
            added_columns.append(column_name)
    
    # 如果添加了 is_identified 欄位，將所有已有身分的用戶設為已識別
    if 'is_identified' in added_columns:
        conn = get_connection()
        with conn:
            with conn.cursor() as cursor:
                sql = """
                UPDATE users_yisin
                SET is_identified = TRUE
                WHERE identity IS NOT NULL
                """
                cursor.execute(sql)
                conn.commit()
                logging.info("已將所有已有身分的用戶設為已識別")
    
    return added_columns

# ============= addresses JSON 資料格式修改 =======================

def generate_new_password(length=4):
    letters = random.choices(string.ascii_letters, k=2)
    digits = random.choices(string.digits, k=2)
    combined = letters + digits
    random.shuffle(combined)
    return ''.join(combined)

def update_address_info(address, new_password):
    addresses_data = load_addresses_data()
    for item in addresses_data:
        if item['address'] == address:
            item['password'] = new_password
            break
    save_addresses_data(addresses_data)
    sync_json_to_db()  # 同步到資料庫

def save_addresses_data(data):
    with open('available_addresses.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    sync_json_to_db()  # 同步到資料庫

def get_address_info(address):
    addresses_data = load_addresses_data()
    for item in addresses_data:
        if item['address'] == address:
            return item
    return None

# 檢查戶別是不是成屋
def is_ready_property(address):
    """檢查戶別是否已完成交屋(已設定保固起算日)"""
    address_info = get_address_info(address)
    return address_info and address_info.get('warranty_start_date') is not None

def load_addresses_data():
    try:
        with open('available_addresses.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def update_address_warranty_start_date(address, start_date):
    """
    更新指定戶別的保固開始日期。
    只有當該戶別的 warranty_start_date 欄位為空時，才會寫入新日期。
    """
    addresses_data = load_addresses_data()
    updated = False
    
    for item in addresses_data:
        if item.get('address') == address:
            # 檢查保固開始日期是否已存在且非空
            if not item.get('warranty_start_date'):
                # 首次寫入保固開始日期
                item['warranty_start_date'] = start_date
                updated = True
            break
            
    if updated:
        save_addresses_data(addresses_data)
        sync_json_to_db()  # 同步到資料庫
        return True # 表示已更新
    return False # 表示未更新（因為日期已存在）
# 在每次修改JSON後同步到資料庫

def sync_json_to_db():
    """同步JSON到資料庫"""
    try:
        # 讀取JSON
        addresses_data = load_addresses_data()
        logging.info(f"從JSON讀取到 {len(addresses_data)} 筆資料")
        
        conn = get_connection()
        with conn:
            with conn.cursor() as cursor:
                # 確保表存在
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS addresses (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    line_user_id VARCHAR(100),
                    full_address VARCHAR(100) NOT NULL UNIQUE,
                    password VARCHAR(20) NOT NULL,
                    warranty_start_date DATE,
                    create_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)
                
                # 同步每條記錄
                success_count = 0
                for item in addresses_data:
                    address = item.get('address')
                    password = item.get('password')
                    warranty_date = item.get('warranty_start_date')
                    
                    if address and password:
                        try:
                            sql = """
                            INSERT INTO addresses (full_address, password, warranty_start_date)
                            VALUES (%s, %s, %s)
                            ON DUPLICATE KEY UPDATE 
                            password = VALUES(password),
                            warranty_start_date = COALESCE(VALUES(warranty_start_date), warranty_start_date)
                            """
                            cursor.execute(sql, (address, password, warranty_date))
                            success_count += 1
                        except Exception as e:
                            logging.error(f"同步戶別 {address} 失敗: {e}")
                
                conn.commit()
                logging.info(f"成功同步 {success_count}/{len(addresses_data)} 筆戶別資料")
                
        return True
    except Exception as e:
        logging.error(f"同步JSON到資料庫失敗: {e}")
        logging.exception("詳細錯誤")
        return False
    
def check_addresses_table():
    conn = get_connection()
    with conn:
        with conn.cursor() as cursor:
            cursor.execute("""
            SELECT COUNT(*) as count 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = %s 
            AND TABLE_NAME = 'addresses'
            """, (os.getenv("DB_NAME"),))
            result = cursor.fetchone()
            exists = result and result['count'] > 0
            if exists:
                # 查看表中有多少記錄
                cursor.execute("SELECT COUNT(*) as count FROM addresses")
                count = cursor.fetchone()['count']
                print(f"addresses表存在，共有{count}筆記錄")
            else:
                print("addresses表不存在")
            return exists
def force_sync_json_to_db():
    print("開始強制同步JSON到資料庫...")
    result = sync_json_to_db()
    if result:
        # 查詢記錄數
        conn = get_connection()
        with conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as count FROM addresses")
                count = cursor.fetchone()['count']
                print(f"同步成功，addresses表有{count}筆記錄")
    else:
        print("同步失敗")
    return result

if __name__ == "__main__":
    try:
        print("正在測試資料庫連線...")
        connection = get_connection()
        print("資料庫連線測試成功")
        connection.close()
        
        # 確保所有必要的欄位都存在
        added_columns = ensure_all_required_columns()
        if added_columns:
            print(f"已添加以下欄位到數據庫: {', '.join(added_columns)}")
        else:
            print("所有必要的欄位已存在")
        
    except Exception as e:
        print(f"資料庫連線測試失敗: {e}")