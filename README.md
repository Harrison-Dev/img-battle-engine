# Image Battle Engine 圖戰引擎

> 此專案使用 [Cursor](https://cursor.sh/) AI輔助開發

https://img-battle-engine.harrison-chen.dev/
高性能視頻幀搜索和提取服務，專門用於快速檢索視頻中的特定場景。

## 主要功能

- 🔍 高效全文搜索
  - 支持中文分詞
  - 模糊搜索
  - 相關度排序
  - 可自定義結果數量

- 🖼️ 智能幀提取
  - 精確時間點定位
  - 高質量圖片輸出
  - 支持多種視頻格式

- 📦 數據管理
  - CSV 數據導入
  - 預建索引機制
  - 內存緩存層

## 技術棧

- [Gin](https://github.com/gin-gonic/gin) - Web框架
- [Bleve](https://github.com/blevesearch/bleve) - 全文搜索引擎
- [FFmpeg](https://ffmpeg.org/) - 視頻處理
- [GraphQL](https://graphql.org/) - API查詢語言

## 快速開始

### 前置需求

- Go 1.20+
- FFmpeg
- Git

### 安裝

```bash
# 克隆倉庫
git clone git@github.com:Harrison-Dev/img-battle-engine.git
cd img-battle-engine

# 安裝依賴
go mod download
```

### 配置

1. 準備數據文件
   - 在 `tables/` 目錄下放置CSV文件
   - 在 `contents/` 目錄下放置視頻文件
   - 確保 `tables/schema.yml` 配置正確

2. CSV 格式要求
```csv
id,score,text,episode,start_time,end_time,start_frame,end_frame
xxx,1.0,對話內容,1,"00:00:38,329","00:00:40,247",918,964
```

### 運行

```bash
go run main.go
```

訪問 http://localhost:8080 使用Web界面

## API 使用

### GraphQL API

搜索接口：
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

獲取幀圖片：
```
GET /frame/:id
```

## 項目結構

```
.
├── api/            # API處理器和路由
│   ├── graphql/    # GraphQL相關
│   └── static/     # 靜態文件
├── core/           # 核心業務邏輯
│   ├── search/     # 搜索引擎
│   └── extract/    # 幀提取
├── config/         # 配置文件
├── tables/         # 數據文件
└── contents/       # 視頻文件
```

## 開發

### 運行測試

```bash
go test ./... -v
```

### 代碼風格

```bash
go fmt ./...
golangci-lint run
```

## 貢獻指南

1. Fork 本倉庫
2. 創建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

## 授權協議

本項目採用 MIT 授權協議 - 查看 [LICENSE](LICENSE) 文件了解更多細節
