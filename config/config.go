package config

import (
	"os"
	"path/filepath"

	"gopkg.in/yaml.v2"
)

type VideoFormat struct {
	Extension       string `yaml:"extension"`
	NamingPattern   string `yaml:"naming_pattern"`
	FrameExtraction struct {
		Format  string `yaml:"format"`
		Quality int    `yaml:"quality"`
	} `yaml:"frame_extraction"`
}

type Field struct {
	Name        string `yaml:"name"`
	Type        string `yaml:"type"`
	PrimaryKey  bool   `yaml:"primary_key"`
	Index       bool   `yaml:"index"`
	Description string `yaml:"description"`
}

type Collection struct {
	TableFile   string      `yaml:"table_file"`
	ContentDir  string      `yaml:"content_dir"`
	Fields      []Field     `yaml:"fields"`
	VideoFormat VideoFormat `yaml:"video_format"`
}

type Config struct {
	Collections map[string]Collection `yaml:"collections"`
}

func LoadConfig(configPath string) (*Config, error) {
	data, err := os.ReadFile(configPath)
	if err != nil {
		return nil, err
	}

	var config Config
	if err := yaml.Unmarshal(data, &config); err != nil {
		return nil, err
	}

	return &config, nil
}

func GetAbsolutePath(basePath, relativePath string) string {
	if filepath.IsAbs(relativePath) {
		return relativePath
	}
	return filepath.Join(basePath, relativePath)
}
