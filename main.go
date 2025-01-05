package main

import (
	"fmt"
	"log"
	"net/http"
	"path/filepath"

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

	// 幀提取endpoint
	r.GET("/frame/:id", func(c *gin.Context) {
		id := c.Param("id")

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

		// 提取幀
		frame, err := frameProvider.ExtractFrame(videoPath, targetResult.StartTime)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("Failed to extract frame: %v", err)})
			return
		}

		c.Data(http.StatusOK, "image/jpeg", frame)
	})

	log.Printf("Server starting at http://localhost:8080")
	if err := r.Run(":8080"); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
