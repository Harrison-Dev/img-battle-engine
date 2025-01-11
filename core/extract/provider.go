package extract

import (
	"fmt"
	"log"
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
	log.Printf("[ParseTimeCode] Parsing timecode: %s", tc)
	parts := strings.Split(tc, ",")
	if len(parts) != 2 {
		log.Printf("[ParseTimeCode] Error: Invalid timecode format: %s", tc)
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

	log.Printf("[ParseTimeCode] Successfully parsed timecode: %02d:%02d:%02d,%03d",
		timeCode.Hours, timeCode.Minutes, timeCode.Seconds, timeCode.Millis)
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
		log.Printf("[NewMPEGProvider] Error: ffmpeg not found in PATH")
		return nil, fmt.Errorf("ffmpeg not found: %v", err)
	}
	log.Printf("[NewMPEGProvider] Found ffmpeg at: %s", ffmpegPath)
	return &MPEGProvider{ffmpegPath: ffmpegPath}, nil
}

// ExtractFrame 從MPEG視頻中提取指定時間點的幀
func (p *MPEGProvider) ExtractFrame(videoPath string, timeCode string) ([]byte, error) {
	log.Printf("[ExtractFrame] Starting extraction - Video: %s, TimeCode: %s", videoPath, timeCode)

	// 檢查視頻文件是否存在
	if _, err := os.Stat(videoPath); os.IsNotExist(err) {
		log.Printf("[ExtractFrame] Error: Video file not found at path: %s", videoPath)
		return nil, fmt.Errorf("video file not found: %s", videoPath)
	}

	tc, err := ParseTimeCode(timeCode)
	if err != nil {
		log.Printf("[ExtractFrame] Error parsing timecode '%s': %v", timeCode, err)
		return nil, err
	}

	// 創建臨時文件
	tmpFile := filepath.Join(os.TempDir(), fmt.Sprintf("frame_%d.jpg", time.Now().UnixNano()))
	log.Printf("[ExtractFrame] Using temporary file: %s", tmpFile)
	defer func() {
		if err := os.Remove(tmpFile); err != nil {
			log.Printf("[ExtractFrame] Warning: Failed to remove temporary file %s: %v", tmpFile, err)
		}
	}()

	// 構建 ffmpeg 命令
	seconds := tc.ToSeconds()
	args := []string{
		"-ss", fmt.Sprintf("%f", seconds),
		"-i", videoPath,
		"-vframes", "1",
		"-q:v", "2",
		"-f", "image2",
		tmpFile,
	}
	
	log.Printf("[ExtractFrame] Executing ffmpeg command: %s %v", p.ffmpegPath, args)
	cmd := exec.Command(p.ffmpegPath, args...)

	// 捕獲命令輸出
	output, err := cmd.CombinedOutput()
	if err != nil {
		log.Printf("[ExtractFrame] FFmpeg error: %v\nOutput: %s", err, string(output))
		return nil, fmt.Errorf("failed to extract frame: %v (output: %s)", err, string(output))
	}

	// 檢查輸出文件是否存在
	if _, err := os.Stat(tmpFile); os.IsNotExist(err) {
		log.Printf("[ExtractFrame] Error: Frame file was not created at %s", tmpFile)
		return nil, fmt.Errorf("frame file was not created")
	}

	// 讀取生成的圖片
	frameData, err := os.ReadFile(tmpFile)
	if err != nil {
		log.Printf("[ExtractFrame] Error reading frame file %s: %v", tmpFile, err)
		return nil, fmt.Errorf("failed to read frame file: %v", err)
	}

	log.Printf("[ExtractFrame] Successfully extracted frame - Size: %d bytes", len(frameData))
	return frameData, nil
}
