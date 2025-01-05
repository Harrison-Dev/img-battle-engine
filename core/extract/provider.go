package extract

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

// TimeCode 表示視頻時間碼
type TimeCode struct {
	Hours   int
	Minutes int
	Seconds int
	Millis  int
}

// ParseTimeCode 解析時間碼字符串
func ParseTimeCode(tc string) (*TimeCode, error) {
	parts := strings.Split(tc, ",")
	if len(parts) != 2 {
		return nil, fmt.Errorf("invalid timecode format: %s", tc)
	}

	timeParts := strings.Split(parts[0], ":")
	if len(timeParts) != 3 {
		return nil, fmt.Errorf("invalid time format: %s", parts[0])
	}

	var timeCode TimeCode
	var err error
	var n int

	// 解析小時
	n, err = fmt.Sscanf(timeParts[0], "%d", &timeCode.Hours)
	if err != nil || n != 1 {
		return nil, fmt.Errorf("invalid hours format: %s", timeParts[0])
	}

	// 解析分鐘
	n, err = fmt.Sscanf(timeParts[1], "%d", &timeCode.Minutes)
	if err != nil || n != 1 {
		return nil, fmt.Errorf("invalid minutes format: %s", timeParts[1])
	}

	// 解析秒數
	n, err = fmt.Sscanf(timeParts[2], "%d", &timeCode.Seconds)
	if err != nil || n != 1 {
		return nil, fmt.Errorf("invalid seconds format: %s", timeParts[2])
	}

	// 解析毫秒
	n, err = fmt.Sscanf(parts[1], "%d", &timeCode.Millis)
	if err != nil || n != 1 {
		return nil, fmt.Errorf("invalid milliseconds format: %s", parts[1])
	}

	// 驗證數值範圍
	if timeCode.Hours < 0 || timeCode.Minutes < 0 || timeCode.Minutes >= 60 ||
		timeCode.Seconds < 0 || timeCode.Seconds >= 60 || timeCode.Millis < 0 || timeCode.Millis >= 1000 {
		return nil, fmt.Errorf("time values out of range: %02d:%02d:%02d,%03d",
			timeCode.Hours, timeCode.Minutes, timeCode.Seconds, timeCode.Millis)
	}

	return &timeCode, nil
}

// ToSeconds 將時間碼轉換為秒數
func (tc *TimeCode) ToSeconds() float64 {
	return float64(tc.Hours*3600+tc.Minutes*60+tc.Seconds) + float64(tc.Millis)/1000.0
}

// FrameProvider 定義幀提取接口
type FrameProvider interface {
	ExtractFrame(videoPath string, timeCode string) ([]byte, error)
}

// MPEGProvider 實現MPEG視頻的幀提取
type MPEGProvider struct {
	ffmpegPath string
}

// NewMPEGProvider 創建新的MPEG提供者
func NewMPEGProvider() (*MPEGProvider, error) {
	ffmpegPath, err := exec.LookPath("ffmpeg")
	if err != nil {
		return nil, fmt.Errorf("ffmpeg not found: %v", err)
	}
	return &MPEGProvider{ffmpegPath: ffmpegPath}, nil
}

// ExtractFrame 從MPEG視頻中提取指定時間點的幀
func (p *MPEGProvider) ExtractFrame(videoPath string, timeCode string) ([]byte, error) {
	tc, err := ParseTimeCode(timeCode)
	if err != nil {
		return nil, err
	}

	// 創建臨時文件
	tmpFile := filepath.Join(os.TempDir(), fmt.Sprintf("frame_%d.jpg", time.Now().UnixNano()))
	defer os.Remove(tmpFile)

	// 使用ffmpeg提取幀
	cmd := exec.Command(p.ffmpegPath,
		"-ss", fmt.Sprintf("%f", tc.ToSeconds()),
		"-i", videoPath,
		"-vframes", "1",
		"-q:v", "2",
		"-f", "image2",
		tmpFile,
	)

	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("failed to extract frame: %v", err)
	}

	// 讀取生成的圖片
	return os.ReadFile(tmpFile)
}
