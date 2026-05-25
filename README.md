# LINE Bot 雙專案共用倉庫

本倉庫整合兩個高度相似的 LINE Bot 專案：

- YiQi/linebot_for_JayWu-20251109jaywu_complete
- YiSin/linebot_for_JayWu-20251109jaywu_complete

兩個專案使用同一套核心程式架構，差異主要在環境參數、資料庫資料表、部分資料檔與少量行為設定。

## 目錄結構

```text
LINE_bot_JayWu/
├─ YiQi/
│  └─ linebot_for_JayWu-20251109jaywu_complete/
└─ YiSin/
   └─ linebot_for_JayWu-20251109jaywu_complete/
```

## 共同技術堆疊

- Python + Flask (Webhook server)
- line-bot-sdk (LINE Messaging API)
- python-dotenv (.env 載入)
- PyMySQL (MySQL 連線)
- Pillow (Rich Menu 圖片檢查)

## 兩專案差異摘要

以下為目前比對到的主要差異：

- .env 內容不同
- 資料檔不同：addresses.json、available_addresses.json
- 資料表名稱不同：
  - YiQi 專案使用 users_yichi
  - YiSin 專案使用 users_yisin
- line_bot.py 內埠號不同：
  - YiQi: app.run(port=5000)
  - YiSin: app.run(port=3000)
- start_ngrok.bat 設定不同（請對齊實際埠號）
- util/address.py 中部分地址圖片映射不同

## 建議環境變數

每個子專案都應各自有自己的 .env，至少包含：

```env
LINE_CHANNEL_ACCESS_TOKEN=
LINE_CHANNEL_SECRET=
DB_HOST=
DB_USER=
DB_PASSWORD=
DB_NAME=
```

## 安裝與啟動（每個子專案各自執行）

1. 進入任一子專案目錄
2. 建立並啟用虛擬環境
3. 安裝依賴套件
4. 準備 .env
5. 啟動程式

範例（Windows PowerShell）：

```powershell
cd YiQi\linebot_for_JayWu-20251109jaywu_complete
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install flask line-bot-sdk python-dotenv pymysql pillow
python line_bot.py
```

YiSin 專案請把路徑改成 YiSin 對應目錄。

## JSON 搬運到 SQL Server

已提供共用搬運程式：

- scripts/migrate_json_to_sqlserver.py

此程式會把兩種 JSON 匯入 SQL Server，並依專案分流到不同資料表：

- YiQi:
  - addresses.json -> case_names_yiqi
  - available_addresses.json -> available_addresses_yiqi
- YiSin:
  - addresses.json -> case_names_yisin
  - available_addresses.json -> available_addresses_yisin

### 1) 安裝搬運程式依賴

```powershell
pip install -r scripts/requirements-sqlserver.txt
```

### 2) 設定 SQL Server 環境變數

```powershell
$env:SQLSERVER_HOST = "127.0.0.1"
$env:SQLSERVER_PORT = "1433"
$env:SQLSERVER_DB = "linebot"
$env:SQLSERVER_USER = "sa"
$env:SQLSERVER_PASSWORD = "your_password"
$env:SQLSERVER_DRIVER = "ODBC Driver 18 for SQL Server"
$env:SQLSERVER_ENCRYPT = "yes"
$env:SQLSERVER_TRUST_CERT = "yes"
```

若你使用 Windows 驗證，可不設定 SQLSERVER_USER 與 SQLSERVER_PASSWORD。

### 3) 執行搬運

搬運全部專案、全部 JSON：

```powershell
python scripts/migrate_json_to_sqlserver.py --project all --dataset all
```

若你不想先設定環境變數，可直接帶連線參數：

```powershell
python scripts/migrate_json_to_sqlserver.py --project all --dataset all --host 127.0.0.1 --db linebot --user sa --password your_password
```

先檢查目前可用 ODBC 驅動：

```powershell
python scripts/migrate_json_to_sqlserver.py --list-drivers
```

若出現 IM002（找不到驅動），請安裝 Microsoft ODBC Driver 18 for SQL Server，或指定你機器上已存在的驅動名稱：

```powershell
python scripts/migrate_json_to_sqlserver.py --project all --dataset all --host 127.0.0.1 --db linebot --driver "ODBC Driver 17 for SQL Server"
```

若你的 SQL Server 是命名執行個體（例如 `SQLEXPRESS`），請改用 `--instance`，不要帶 `--port`：

```powershell
python scripts/migrate_json_to_sqlserver.py --project all --dataset all --host localhost --instance SQLEXPRESS --db LINE_BOT --driver "SQL Server"
```

也可以在根目錄建立 `.env.sqlserver`（程式會自動讀取）：

```env
SQLSERVER_HOST=127.0.0.1
SQLSERVER_PORT=1433
SQLSERVER_DB=linebot
SQLSERVER_USER=sa
SQLSERVER_PASSWORD=your_password
SQLSERVER_DRIVER=ODBC Driver 18 for SQL Server
SQLSERVER_ENCRYPT=yes
SQLSERVER_TRUST_CERT=yes
```

只搬運 YiQi 的 available_addresses.json：

```powershell
python scripts/migrate_json_to_sqlserver.py --project yiqi --dataset available_addresses
```

只搬運 YiSin 的 addresses.json：

```powershell
python scripts/migrate_json_to_sqlserver.py --project yisin --dataset case_names
```

## JSON 搬運到 MySQL

已提供 MySQL 版搬運程式：

- scripts/migrate_json_to_mysql.py

此程式會把兩種 JSON 匯入 MySQL，並依專案分流到不同資料表：

- YiQi:
  - addresses.json -> case_names_yiqi
  - available_addresses.json -> available_addresses_yiqi
- YiSin:
  - addresses.json -> case_names_yisin
  - available_addresses.json -> available_addresses_yisin

### 1) 安裝依賴

```powershell
pip install -r scripts/requirements-mysql.txt
```

### 2) 準備連線設定

可用 CLI 參數，或使用 `.env` 變數（支援 `DB_USER` 與 `DB_user`）：

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=LINE_BOT
```

### 3) 執行搬運

全部專案、全部資料：

```powershell
python scripts/migrate_json_to_mysql.py --project all --dataset all
```

只搬運 YiQi 的 available_addresses.json：

```powershell
python scripts/migrate_json_to_mysql.py --project yiqi --dataset available_addresses
```

直接帶參數執行（不靠 .env）：

```powershell
python scripts/migrate_json_to_mysql.py --project all --dataset all --host localhost --user root --password your_password --db LINE_BOT
```

## Git 管理原則

- 使用最外層 LINE_bot_JayWu 當作唯一 Git 倉庫根目錄
- 不提交敏感資訊（.env）
- 不提交快取或執行產物（__pycache__、log、venv）
- 兩個子專案都納入同一個版本控制歷史

## 常用 Git 指令

```bash
git status
git add .
git commit -m "chore: add shared root README and gitignore"
git push -u origin main
```

## 備註

- 目前兩專案雖然結構接近，但已存在實際程式與資料差異，後續若要「共用核心程式碼」，建議再做模組化抽離。
