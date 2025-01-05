package extract

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestTimeCodeParsing(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected float64
		hasError bool
	}{
		{
			name:     "正常時間碼",
			input:    "00:01:30,500",
			expected: 90.5,
		},
		{
			name:     "零時間",
			input:    "00:00:00,000",
			expected: 0,
		},
		{
			name:     "一小時",
			input:    "01:00:00,000",
			expected: 3600,
		},
		{
			name:     "無效格式",
			input:    "01:00:00",
			hasError: true,
		},
		{
			name:     "無效數值",
			input:    "aa:bb:cc,ddd",
			hasError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			tc, err := ParseTimeCode(tt.input)
			if tt.hasError {
				assert.Error(t, err)
				return
			}

			assert.NoError(t, err)
			assert.Equal(t, tt.expected, tc.ToSeconds())
		})
	}
}

func TestMPEGProvider(t *testing.T) {
	// 檢查ffmpeg是否可用
	provider, err := NewMPEGProvider()
	if err != nil {
		t.Skip("FFmpeg not available, skipping tests")
	}

	// 創建測試目錄
	testDir := "testdata"
	err = os.MkdirAll(testDir, 0755)
	require.NoError(t, err)
	defer os.RemoveAll(testDir)

	t.Run("提取不存在的視頻", func(t *testing.T) {
		_, err := provider.ExtractFrame("nonexistent.mp4", "00:00:00,000")
		assert.Error(t, err)
	})

	t.Run("無效的時間碼", func(t *testing.T) {
		_, err := provider.ExtractFrame("test.mp4", "invalid")
		assert.Error(t, err)
	})

	// 如果有測試視頻文件，可以添加實際的幀提取測試
	if _, err := os.Stat("testdata/test.mp4"); err == nil {
		t.Run("實際幀提取", func(t *testing.T) {
			frame, err := provider.ExtractFrame(
				filepath.Join(testDir, "test.mp4"),
				"00:00:01,000",
			)
			assert.NoError(t, err)
			assert.NotEmpty(t, frame)
		})
	}
}

func TestFrameProvider(t *testing.T) {
	var provider FrameProvider = &MPEGProvider{}
	assert.Implements(t, (*FrameProvider)(nil), provider)
}
