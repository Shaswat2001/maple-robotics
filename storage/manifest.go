package storage

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
)

// Manifest describes a model and its layers
type Manifest struct {
	SchemaVersion int     `json:"schemaVersion"`
	MediaType     string  `json:"mediaType"`
	Config        Layer   `json:"config"`
	Layers        []Layer `json:"layers"`
}

// Layer is a reference to a blob
type Layer struct {
	MediaType string `json:"mediaType"`
	Digest    string `json:"digest"`
	Size      int64  `json:"size"`
}

// Media types
const (
	MediaTypeManifest = "application/vnd.maple.manifest.v1+json"
	MediaTypeConfig   = "application/vnd.maple.config.v1+json"
	MediaTypeWeights  = "application/vnd.maple.weights"
	MediaTypeLicense  = "application/vnd.maple.license"
)

// ManifestPath returns path for a model manifest
// e.g., openvla:7b -> ~/.maple/manifests/openvla/7b
func ManifestPath(name, tag string) (string, error) {
	dir, err := ManifestsDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, name, tag), nil
}

// ParseModelRef parses "name:tag" into name and tag
// Defaults to "latest" if no tag
func ParseModelRef(ref string) (name, tag string) {
	parts := strings.SplitN(ref, ":", 2)
	name = parts[0]
	if len(parts) > 1 {
		tag = parts[1]
	} else {
		tag = "latest"
	}
	return
}

// SaveManifest writes a manifest to disk
func SaveManifest(name, tag string, m *Manifest) error {
	path, err := ManifestPath(name, tag)
	if err != nil {
		return err
	}

	// Create parent directory
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}

	data, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(path, data, 0644)
}

// LoadManifest reads a manifest from disk
func LoadManifest(name, tag string) (*Manifest, error) {
	path, err := ManifestPath(name, tag)
	if err != nil {
		return nil, err
	}

	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	var m Manifest
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, err
	}

	return &m, nil
}

// ManifestExists checks if a manifest exists
func ManifestExists(name, tag string) (bool, error) {
	path, err := ManifestPath(name, tag)
	if err != nil {
		return false, err
	}
	_, err = os.Stat(path)
	if os.IsNotExist(err) {
		return false, nil
	}
	return err == nil, err
}

// DeleteManifest removes a manifest
func DeleteManifest(name, tag string) error {
	path, err := ManifestPath(name, tag)
	if err != nil {
		return err
	}
	return os.Remove(path)
}

// ListManifests returns all model refs (name:tag)
func ListManifests() ([]string, error) {
	dir, err := ManifestsDir()
	if err != nil {
		return nil, err
	}

	var refs []string

	// Walk manifests directory
	entries, err := os.ReadDir(dir)
	if err != nil {
		if os.IsNotExist(err) {
			return []string{}, nil
		}
		return nil, err
	}

	for _, e := range entries {
		if e.IsDir() {
			name := e.Name()
			// Read tags
			tagDir := filepath.Join(dir, name)
			tags, err := os.ReadDir(tagDir)
			if err != nil {
				continue
			}
			for _, t := range tags {
				if !t.IsDir() {
					refs = append(refs, name+":"+t.Name())
				}
			}
		}
	}

	return refs, nil
}
