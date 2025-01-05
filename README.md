# Image Battle Engine 圖戰引擎

高性能視頻幀搜索和提取服務 (by golang)

## 功能特點

- 高效全文搜索
- 快速幀提取
- 預建索引機制
- 內存緩存層

## 技術棧

- [Gin](https://github.com/gin-gonic/gin) - Web框架
- [Bleve](https://github.com/blevesearch/bleve) - 全文搜索引擎
- [FFmpeg](https://ffmpeg.org/) - 視頻處理
- [Docker](https://www.docker.com/) - 容器化
TODO : 需要高效的in-memory db做快速讀取
FFMpeg只是要做某個時間點的frame extrac，如果有更好的框架可用也可以改用那個

## 項目結構

```
.
├── api/            # API處理器和路由
├── core/           # 核心業務邏輯
├── db/             # 數據庫操作
├── config/         # 配置文件
├── docker/         # Docker相關文件
├── scripts/        # 構建和部署腳本
└── test/           # 測試文件
```

## 專案SPEC

此專案主要以兩個micro-service為核心
1. 台詞搜尋引擎
從/tables資料夾中的csv們建立索引(請詳讀csv結構，以及schema yaml)，以及建立一個快速讀取的in-memory db
主要功能為：使用全文搜尋功能，用模糊搜尋的方式，在API要給予n個數量後，篩選出n筆最接近的圖案(score最高)回傳該資料的id，此外不同的csv應該被加入label，API可以使用label篩選需要的table進行搜尋
可以的話，希望用GraphQL來製作API

2. 擷取功能 
目前只實作MPEG provider，從mpeg影片裡面對應檔案擷取frame，之後可能會有其他provider所以這邊代碼要抽象化
一樣要從tables建立的db中，藉由id搜索到資料本身
每一筆資料有以下欄位：
```
id,score,text,episode,start_time,end_time,start_frame,end_frame
```
根據找到的資料的 episode 去對應資料夾底下找尋該檔案
例如mygo csv裡面 第二筆資料為
```
LQulFI8BYtCDorbFC2yp,1.0,傳訊息也都沒有回,1,"00:00:38,329","00:00:40,247",918,964
```
找到這筆資料時，就要去/contents資料夾底下，先找到mygo資料夾，在該資料夾底下找尋episode值，例如這裡是1
就是1.mp4，在此檔案的對應秒數 00:00:38,329 ~ 00:00:40,247區間範圍內，隨意挑一個frame截圖成JPEG回傳給用戶
所以這個api就是輸入id輸出jpeg檔案

如果這些資料夾名稱的關聯需要設定檔，請修改schema.yaml的設計來達成目標