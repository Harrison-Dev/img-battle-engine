package search

import (
	"encoding/csv"
	"fmt"
	"io"
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
	// 設置CSV讀取器選項
	reader.FieldsPerRecord = -1 // 允許變長記錄
	reader.TrimLeadingSpace = true
	reader.LazyQuotes = true

	// 跳過標題行
	headers, err := reader.Read()
	if err != nil {
		return fmt.Errorf("failed to read CSV header: %v", err)
	}

	// 驗證必要的列
	requiredColumns := []string{"id", "text", "episode", "start_time", "end_time", "start_frame", "end_frame"}
	columnMap := make(map[string]int)
	for i, header := range headers {
		columnMap[header] = i
	}
	for _, col := range requiredColumns {
		if _, exists := columnMap[col]; !exists {
			return fmt.Errorf("required column '%s' not found in CSV", col)
		}
	}

	// 確保集合的數據map已初始化
	if e.data[collection] == nil {
		e.data[collection] = make(map[string]SearchResult)
	}

	var results []SearchResult
	lineNum := 1
	for {
		record, err := reader.Read()
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("error reading CSV line %d: %v", lineNum, err)
		}

		// 驗證記錄長度
		if len(record) < len(headers) {
			return fmt.Errorf("invalid record at line %d: expected %d fields, got %d",
				lineNum, len(headers), len(record))
		}

		// 解析episode
		episode, err := strconv.Atoi(record[columnMap["episode"]])
		if err != nil {
			return fmt.Errorf("invalid episode number at line %d: %v", lineNum, err)
		}

		// 驗證時間格式
		startTime := record[columnMap["start_time"]]
		endTime := record[columnMap["end_time"]]
		if _, err := ParseTimeCode(startTime); err != nil {
			return fmt.Errorf("invalid start_time at line %d: %v", lineNum, err)
		}
		if _, err := ParseTimeCode(endTime); err != nil {
			return fmt.Errorf("invalid end_time at line %d: %v", lineNum, err)
		}

		// 驗證幀編號
		startFrame, err := strconv.Atoi(record[columnMap["start_frame"]])
		if err != nil {
			return fmt.Errorf("invalid start_frame at line %d: %v", lineNum, err)
		}
		endFrame, err := strconv.Atoi(record[columnMap["end_frame"]])
		if err != nil {
			return fmt.Errorf("invalid end_frame at line %d: %v", lineNum, err)
		}

		// 創建搜索結果
		result := SearchResult{
			ID:         record[columnMap["id"]],
			Score:      1.0,
			Text:       record[columnMap["text"]],
			Episode:    episode,
			StartTime:  startTime,
			EndTime:    endTime,
			Collection: collection,
		}

		// 驗證時間和幀的一致性
		if startFrame >= endFrame {
			return fmt.Errorf("invalid frame range at line %d: start_frame >= end_frame", lineNum)
		}

		results = append(results, result)
		e.data[collection][result.ID] = result
		lineNum++
	}

	if len(results) == 0 {
		return fmt.Errorf("no valid records found in CSV file")
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
