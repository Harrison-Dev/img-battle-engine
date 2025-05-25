# Image Battle Engine 圖戰引擎

> 此專案使用 [Cursor](https://cursor.sh/) AI 輔助開發

[https://img-battle-engine.harrison-chen.dev/](https://img-battle-engine.harrison-chen.dev/)

高效能影片影格搜尋和擷取服務，專門用於快速檢索影片中的特定場景。

## 主要功能

* 🔍 高效全文搜尋

  * 支援中文分詞
  * 模糊搜尋
  * 相關度排序
  * 可自訂結果數量

* 🖼️ 智能影格擷取

  * 精準時間點定位
  * 高品質圖片輸出
  * 支援多種影片格式

* 📦 資料管理

  * CSV 資料匯入
  * 預先建置索引機制
  * 記憶體快取層

## 技術堆疊

* [Gin](https://github.com/gin-gonic/gin) – Web 框架
* [Bleve](https://github.com/blevesearch/bleve) – 全文搜尋引擎
* [FFmpeg](https://ffmpeg.org/) – 影片處理
* [GraphQL](https://graphql.org/) – API 查詢語言

## 快速開始

### 先決條件

* Go 1.20+
* FFmpeg
* Git

### 安裝

```bash
# 分叉倉庫
git clone git@github.com:Harrison-Dev/img-battle-engine.git
cd img-battle-engine

# 安裝相依套件
go mod download
```

### 設定

1. 準備資料檔案

   * 在 `tables/` 資料夾放置 CSV 檔案
   * 在 `contents/` 資料夾放置影片檔案
   * 確保 `tables/schema.yml` 設定正確

2. CSV 檔案格式要求

   ```csv
   id,score,text,episode,start_time,end_time,start_frame,end_frame
   xxx,1.0,對話內容,1,"00:00:38,329","00:00:40,247",918,964
   ```

### 執行

```bash
go run main.go
```

存取 [http://localhost:8080](http://localhost:8080) 使用網頁介面

## API 使用方式

### GraphQL API

搜尋介面：

```graphql
query Search($query: String!, $collection: String, $limit: Int) {
    search(query: $query, collection: $collection, limit: $limit) {
        id
        score
        text
        episode
        startTime
        endTime
        collection
    }
}
```

### REST API

取得影格圖片：

```
GET /frame/:id
```

## 專案結構

```
.
├── api/            # API 處理器與路由
│   ├── graphql/    # GraphQL 相關
│   └── static/     # 靜態檔案
├── core/           # 核心業務邏輯
│   ├── search/     # 搜尋引擎
│   └── extract/    # 影格擷取
├── config/         # 設定檔
├── tables/         # 資料檔案
└── contents/       # 影片檔案
```

## 開發

### 執行測試

```bash
go test ./... -v
```

### 程式碼風格

```bash
go fmt ./...
golangci-lint run
```

## 貢獻指南

1. Fork 本倉庫
2. 建立功能分支 (`git checkout -b feature/AmazingFeature`)
3. 送出變更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送至分支 (`git push origin feature/AmazingFeature`)
5. 提出 Pull Request

## 授權條款

本專案採用 MIT 授權條款 — 查看 [LICENSE](LICENSE) 了解更多細節。
