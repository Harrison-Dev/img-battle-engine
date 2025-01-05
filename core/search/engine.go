package search

import (
	"encoding/csv"
	"fmt"
	"os"
	"strconv"

	"github.com/blevesearch/bleve/v2"
	"github.com/blevesearch/bleve/v2/analysis/analyzer/keyword"
	"github.com/blevesearch/bleve/v2/analysis/lang/cjk"
	"github.com/blevesearch/bleve/v2/mapping"
	"github.com/img-battle-engine/config"
)

// SearchResult 表示搜索結果
type SearchResult struct {
	ID         string  `json:"id"`
	Score      float64 `json:"score"`
	Text       string  `json:"text"`
	Episode    int     `json:"episode"`
	StartTime  string  `json:"start_time"`
	EndTime    string  `json:"end_time"`
	Collection string  `json:"collection"`
}

// SearchEngine 定義搜索引擎接口
type SearchEngine interface {
	Search(query string, collection string, limit int) ([]SearchResult, error)
	Index(collection string, data []SearchResult) error
	LoadCSV(collection string, csvPath string) error
}

// BleveSearchEngine 實現基於Bleve的搜索引擎
type BleveSearchEngine struct {
	indices map[string]bleve.Index
	config  *config.Config
	data    map[string]map[string]SearchResult // collection -> id -> result
}

// createIndexMapping 創建索引映射
func createIndexMapping() mapping.IndexMapping {
	indexMapping := bleve.NewIndexMapping()

	// 使用內置的CJK分析器
	indexMapping.DefaultAnalyzer = cjk.AnalyzerName

	// 創建文本字段映射
	textFieldMapping := bleve.NewTextFieldMapping()
	textFieldMapping.Analyzer = cjk.AnalyzerName

	// 創建關鍵字字段映射
	keywordFieldMapping := bleve.NewTextFieldMapping()
	keywordFieldMapping.Analyzer = keyword.Name

	// 創建數字字段映射
	numericFieldMapping := bleve.NewNumericFieldMapping()

	// 創建文檔映射
	documentMapping := bleve.NewDocumentMapping()
	documentMapping.AddFieldMappingsAt("text", textFieldMapping)
	documentMapping.AddFieldMappingsAt("id", keywordFieldMapping)
	documentMapping.AddFieldMappingsAt("episode", numericFieldMapping)

	indexMapping.DefaultMapping = documentMapping

	return indexMapping
}

// NewBleveSearchEngine 創建新的Bleve搜索引擎實例
func NewBleveSearchEngine(cfg *config.Config) (*BleveSearchEngine, error) {
	engine := &BleveSearchEngine{
		indices: make(map[string]bleve.Index),
		config:  cfg,
		data:    make(map[string]map[string]SearchResult),
	}

	// 為每個集合創建或打開索引
	for name := range cfg.Collections {
		indexPath := name + ".bleve"
		var index bleve.Index
		var err error

		// 嘗試打開現有索引
		index, err = bleve.Open(indexPath)
		if err != nil {
			// 如果索引不存在，創建新索引
			if err == bleve.ErrorIndexPathDoesNotExist {
				indexMapping := createIndexMapping()
				index, err = bleve.New(indexPath, indexMapping)
				if err != nil {
					return nil, fmt.Errorf("failed to create index %s: %v", name, err)
				}
			} else {
				return nil, fmt.Errorf("failed to open index %s: %v", name, err)
			}
		}

		engine.indices[name] = index
		engine.data[name] = make(map[string]SearchResult)
	}

	return engine, nil
}

// LoadCSV 從CSV文件加載數據
func (e *BleveSearchEngine) LoadCSV(collection string, csvPath string) error {
	// 檢查集合是否存在
	if _, exists := e.indices[collection]; !exists {
		return fmt.Errorf("collection not found: %s", collection)
	}

	file, err := os.Open(csvPath)
	if err != nil {
		return fmt.Errorf("failed to open CSV file: %v", err)
	}
	defer file.Close()

	reader := csv.NewReader(file)
	// 跳過標題行
	if _, err := reader.Read(); err != nil {
		return fmt.Errorf("failed to read CSV header: %v", err)
	}

	// 確保集合的數據map已初始化
	if e.data[collection] == nil {
		e.data[collection] = make(map[string]SearchResult)
	}

	var results []SearchResult
	for {
		record, err := reader.Read()
		if err != nil {
			break // EOF或其他錯誤
		}

		episode, _ := strconv.Atoi(record[3])
		result := SearchResult{
			ID:         record[0],
			Score:      1.0,
			Text:       record[2],
			Episode:    episode,
			StartTime:  record[4],
			EndTime:    record[5],
			Collection: collection,
		}

		results = append(results, result)
		e.data[collection][result.ID] = result
	}

	return e.Index(collection, results)
}

// Search 實現搜索功能
func (e *BleveSearchEngine) Search(query string, collection string, limit int) ([]SearchResult, error) {
	if index, exists := e.indices[collection]; exists {
		// 創建複合查詢
		textQuery := bleve.NewMatchPhraseQuery(query)
		textQuery.SetField("text")
		textQuery.SetBoost(2.0) // 提高短語匹配的權重

		fuzzyQuery := bleve.NewFuzzyQuery(query)
		fuzzyQuery.SetField("text")
		fuzzyQuery.SetFuzziness(1)
		fuzzyQuery.SetBoost(0.5) // 降低模糊匹配的權重

		booleanQuery := bleve.NewBooleanQuery()
		booleanQuery.AddShould(textQuery)
		booleanQuery.AddShould(fuzzyQuery)

		searchRequest := bleve.NewSearchRequest(booleanQuery)
		searchRequest.Size = limit
		searchRequest.Fields = []string{"*"}

		searchResults, err := index.Search(searchRequest)
		if err != nil {
			return nil, err
		}

		results := make([]SearchResult, 0, len(searchResults.Hits))
		for _, hit := range searchResults.Hits {
			if result, ok := e.data[collection][hit.ID]; ok {
				result.Score = hit.Score
				results = append(results, result)
			}
		}

		return results, nil
	}
	return nil, fmt.Errorf("collection not found: %s", collection)
}

// Index 實現索引功能
func (e *BleveSearchEngine) Index(collection string, data []SearchResult) error {
	if index, exists := e.indices[collection]; exists {
		batch := index.NewBatch()
		for _, item := range data {
			// 更新內存數據
			e.data[collection][item.ID] = item

			// 索引數據
			if err := batch.Index(item.ID, map[string]interface{}{
				"text":      item.Text,
				"episode":   item.Episode,
				"startTime": item.StartTime,
				"endTime":   item.EndTime,
			}); err != nil {
				return err
			}
		}
		return index.Batch(batch)
	}
	return fmt.Errorf("collection not found: %s", collection)
}

// GetData 返回內部數據存儲
func (e *BleveSearchEngine) GetData() map[string]map[string]SearchResult {
	return e.data
}
