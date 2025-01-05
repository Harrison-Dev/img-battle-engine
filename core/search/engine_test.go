package search

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/img-battle-engine/config"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func setupTestData(t *testing.T) (*BleveSearchEngine, func()) {
	// 創建臨時配置
	cfg := &config.Config{
		Collections: map[string]config.Collection{
			"test": {
				TableFile:  "testdata/test.csv",
				ContentDir: "testdata/content",
			},
		},
	}

	// 創建測試目錄
	err := os.MkdirAll("testdata", 0755)
	require.NoError(t, err)

	// 創建測試CSV文件
	testCSV := `id,score,text,episode,start_time,end_time,start_frame,end_frame
test001,1.0,這是一個測試句子,1,"00:01:00,000","00:01:02,000",1000,1050
test002,1.0,另一個不同的句子,1,"00:01:02,000","00:01:04,000",2000,2050
test003,1.0,完全不相關的內容,2,"00:01:30,000","00:01:32,000",1500,1550
test004,1.0,測試搜索引擎功能,2,"00:01:32,000","00:01:34,000",1551,1600
test005,1.0,這個句子包含測試關鍵詞,3,"00:01:34,000","00:01:36,000",1601,1650`

	err = os.WriteFile(filepath.Join("testdata", "test.csv"), []byte(testCSV), 0644)
	require.NoError(t, err)

	// 初始化搜索引擎
	engine, err := NewBleveSearchEngine(cfg)
	require.NoError(t, err)

	// 加載測試數據
	err = engine.LoadCSV("test", filepath.Join("testdata", "test.csv"))
	require.NoError(t, err)

	// 返回清理函數
	cleanup := func() {
		os.RemoveAll("testdata")
		os.RemoveAll("test.bleve")
	}

	return engine, cleanup
}

func TestBleveSearchEngine(t *testing.T) {
	engine, cleanup := setupTestData(t)
	defer cleanup()

	tests := []struct {
		name          string
		query         string
		collection    string
		limit         int
		expectedCount int
		expectedIDs   []string
		expectError   bool
	}{
		{
			name:          "精確搜索測試",
			query:         "測試句子",
			collection:    "test",
			limit:         10,
			expectedCount: 1,
			expectedIDs:   []string{"test001"},
		},
		{
			name:          "模糊搜索測試",
			query:         "測試",
			collection:    "test",
			limit:         10,
			expectedCount: 3,
			expectedIDs:   []string{"test001", "test004", "test005"},
		},
		{
			name:          "無結果搜索測試",
			query:         "不存在的內容xyz",
			collection:    "test",
			limit:         10,
			expectedCount: 0,
			expectedIDs:   []string{},
		},
		{
			name:          "限制結果數量測試",
			query:         "句子",
			collection:    "test",
			limit:         2,
			expectedCount: 2,
		},
		{
			name:        "錯誤集合名稱測試",
			query:       "測試",
			collection:  "nonexistent",
			limit:       10,
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			results, err := engine.Search(tt.query, tt.collection, tt.limit)

			if tt.expectError {
				assert.Error(t, err)
				return
			}

			assert.NoError(t, err)
			assert.Len(t, results, tt.expectedCount)

			if len(tt.expectedIDs) > 0 {
				actualIDs := make([]string, len(results))
				for i, result := range results {
					actualIDs[i] = result.ID
				}
				assert.Subset(t, actualIDs, tt.expectedIDs)
			}

			// 驗證結果排序（按相關度）
			if len(results) > 1 {
				for i := 1; i < len(results); i++ {
					assert.GreaterOrEqual(t, results[i-1].Score, results[i].Score,
						"結果應該按相關度降序排序")
				}
			}

			// 驗證結果字段
			for _, result := range results {
				assert.NotEmpty(t, result.ID)
				assert.NotEmpty(t, result.Text)
				assert.NotEmpty(t, result.StartTime)
				assert.NotEmpty(t, result.EndTime)
				assert.Greater(t, result.Score, float64(0))
				assert.Greater(t, result.Episode, 0)
			}
		})
	}
}

func TestLoadCSV(t *testing.T) {
	engine, cleanup := setupTestData(t)
	defer cleanup()

	t.Run("加載無效的CSV文件", func(t *testing.T) {
		err := engine.LoadCSV("test", "nonexistent.csv")
		assert.Error(t, err)
	})

	t.Run("加載到無效的集合", func(t *testing.T) {
		err := engine.LoadCSV("nonexistent", "testdata/test.csv")
		assert.Error(t, err)
	})

	t.Run("驗證數據加載", func(t *testing.T) {
		data := engine.GetData()
		assert.NotNil(t, data["test"])
		assert.Equal(t, 5, len(data["test"]))
	})
}

func TestIndexOperations(t *testing.T) {
	engine, cleanup := setupTestData(t)
	defer cleanup()

	t.Run("索引新數據", func(t *testing.T) {
		newData := []SearchResult{
			{
				ID:         "new001",
				Text:       "新添加的測試數據",
				Episode:    1,
				StartTime:  "00:00:00,000",
				EndTime:    "00:00:02,000",
				Collection: "test",
			},
		}

		err := engine.Index("test", newData)
		assert.NoError(t, err)

		// 驗證新數據可以被搜索到
		results, err := engine.Search("新添加", "test", 10)
		assert.NoError(t, err)
		assert.Len(t, results, 1)
		assert.Equal(t, "new001", results[0].ID)
	})

	t.Run("索引到無效集合", func(t *testing.T) {
		err := engine.Index("nonexistent", []SearchResult{})
		assert.Error(t, err)
	})
}
