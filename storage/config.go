package storage

import (
	"encoding/json"
)

// Config holds model metadata
type Config struct {
	// Model info
	Architecture  string `json:"architecture"`   // openvla, groot, smolvla
	Family        string `json:"family"`         // llama, qwen, etc.
	ParameterSize string `json:"parameter_size"` // 7B, 3B, etc.

	// VLA-specific
	ActionDim int `json:"action_dim"` // action dimension (e.g., 7)
	ImageSize int `json:"image_size"` // input image size (e.g., 224)

	// Environment compatibility
	Environments []string `json:"environments"` // libero, aloha, robocasa

	// For loading
	HFRepo        string `json:"hf_repo,omitempty"`        // source HuggingFace repo
	EmbodimentTag string `json:"embodiment_tag,omitempty"` // for GR00T
	DataConfig    string `json:"data_config,omitempty"`    // for GR00T
}

// ConfigFromJSON parses config from JSON bytes
func ConfigFromJSON(data []byte) (*Config, error) {
	var c Config
	if err := json.Unmarshal(data, &c); err != nil {
		return nil, err
	}
	return &c, nil
}

// ToJSON converts config to JSON bytes
func (c *Config) ToJSON() ([]byte, error) {
	return json.MarshalIndent(c, "", "  ")
}

// LoadConfig loads config from a manifest's config layer
func LoadConfig(name, tag string) (*Config, error) {
	m, err := LoadManifest(name, tag)
	if err != nil {
		return nil, err
	}

	// Open the config blob
	f, err := OpenBlob(m.Config.Digest)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	// Read and parse
	data := make([]byte, m.Config.Size)
	if _, err := f.Read(data); err != nil {
		return nil, err
	}

	return ConfigFromJSON(data)
}
