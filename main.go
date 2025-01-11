package main

import (
	"fmt"
	"log"
	"net/http"
	"path/filepath"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	gql "github.com/graphql-go/graphql"
	apigql "github.com/img-battle-engine/api/graphql"
	"github.com/img-battle-engine/config"
	"github.com/img-battle-engine/core/extract"
	"github.com/img-battle-engine/core/search"
)

// 全局變量，用於保存搜索引擎實例
var (
	globalSearchEngine *search.BleveSearchEngine
	globalConfig       *config.Config
	globalFrameProvider *extract.MPEGProvider
)

func main() {
	// 加載配置
	cfg, err := config.LoadConfig("tables/schema.yml")
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}
	globalConfig = cfg

	// 初始化搜索引擎
	searchEngine, err := search.NewBleveSearchEngine(cfg)
	if err != nil {
		log.Fatalf("Failed to create search engine: %v", err)
	}
	globalSearchEngine = searchEngine

	// 加載數據
	for name, collection := range cfg.Collections {
		if err := searchEngine.LoadCSV(name, collection.TableFile); err != nil {
			log.Fatalf("Failed to load CSV for %s: %v", name, err)
		}
	}

	// 初始化幀提取器
	frameProvider, err := extract.NewMPEGProvider()
	if err != nil {
		log.Fatalf("Failed to create frame provider: %v", err)
	}
	globalFrameProvider = frameProvider

	// 設置GraphQL schema
	schema, err := apigql.NewSchema(searchEngine)
	if err != nil {
		log.Fatalf("Failed to create GraphQL schema: %v", err)
	}

	// 設置Gin路由
	r := gin.Default()

	// 靜態文件服務
	r.LoadHTMLGlob("api/static/*.html")
	r.GET("/", func(c *gin.Context) {
		c.HTML(http.StatusOK, "index.html", nil)
	})
	r.HEAD("/", func(c *gin.Context) {
		c.Status(http.StatusOK)
	})

	// 獲取所有可用集合
	r.GET("/collections", func(c *gin.Context) {
		collections := make([]string, 0, len(globalConfig.Collections))
		for name := range globalConfig.Collections {
			collections = append(collections, name)
		}
		c.JSON(http.StatusOK, gin.H{
			"collections": collections,
		})
	})

	// GraphQL endpoint
	r.POST("/graphql", func(c *gin.Context) {
		var request struct {
			Query     string                 `json:"query"`
			Variables map[string]interface{} `json:"variables"`
		}

		if err := c.BindJSON(&request); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		result := gql.Do(gql.Params{
			Schema:         schema,
			RequestString:  request.Query,
			VariableValues: request.Variables,
		})

		c.JSON(http.StatusOK, result)
	})

	// 幀提取endpoint - 使用單一路由處理所有請求
	r.GET("/frame/*path", handleFrame)

	log.Printf("Server starting at http://localhost:8080")
	if err := r.Run(":8080"); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}

// handleFrame 處理幀提取請求
func handleFrame(c *gin.Context) {
	// 從路徑參數中提取ID，並去除可能的.jpg後綴和前導斜線
	path := strings.TrimPrefix(c.Param("path"), "/")
	id := strings.TrimSuffix(path, ".jpg")

	// 在所有集合中查找對應的ID
	var targetResult *search.SearchResult
	var collectionName string

	for name, collection := range globalSearchEngine.GetData() {
		if result, exists := collection[id]; exists {
			targetResult = &result
			collectionName = name
			break
		}
	}

	if targetResult == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "ID not found"})
		return
	}

	// 獲取視頻文件路徑
	collectionConfig := globalConfig.Collections[collectionName]
	videoFileName := fmt.Sprintf("%d.mp4", targetResult.Episode)
	videoPath := filepath.Join(collectionConfig.ContentDir, videoFileName)

	// 生成穩定的 ETag
	etag := fmt.Sprintf("%s-%d-%d", id, targetResult.StartTime, targetResult.Episode)
	lastModified := time.Date(2025, 1, 1, 0, 0, 0, 0, time.UTC)
	
	// 檢查 If-None-Match 頭
	if match := c.GetHeader("If-None-Match"); match == etag {
		c.Status(http.StatusNotModified)
		return
	}

	// 檢查 If-Modified-Since 頭
	if since := c.GetHeader("If-Modified-Since"); since != "" {
		if t, err := time.Parse(http.TimeFormat, since); err == nil {
			if !lastModified.After(t) {
				c.Status(http.StatusNotModified)
				return
			}
		}
	}

	// 提取幀
	frame, err := globalFrameProvider.ExtractFrame(videoPath, targetResult.StartTime)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("Failed to extract frame: %v", err)})
		return
	}

	// 設置緩存頭
	c.Header("Cache-Control", "public, max-age=604800, immutable") // 7天，添加 immutable
	c.Header("ETag", etag)
	c.Header("Last-Modified", lastModified.Format(http.TimeFormat))
	c.Header("Vary", "Accept-Encoding")
	c.Header("CDN-Cache-Control", "max-age=604800") // 特別告訴 CDN 可以緩存
	c.Header("Surrogate-Control", "max-age=604800") // 另一種 CDN 緩存控制頭
	c.Header("Age", "0") // 告訴 CDN 這是新鮮的內容

	c.Data(http.StatusOK, "image/jpeg", frame)
}
