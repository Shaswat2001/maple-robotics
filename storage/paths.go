package storage

import (
	"os"
	"path/filepath"
)

// Root returns the MAPLE home directory (~/.maple)
func Root() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(home, ".maple"), nil
}

// BlobsDir returns the blobs directory (~/.maple/blobs)
func BlobsDir() (string, error) {
	root, err := Root()
	if err != nil {
		return "", err
	}
	return filepath.Join(root, "blobs"), nil
}

// ManifestsDir returns the manifests directory (~/.maple/manifests)
func ManifestsDir() (string, error) {
	root, err := Root()
	if err != nil {
		return "", err
	}
	return filepath.Join(root, "manifests"), nil
}

// EnsureDirs creates all required directories
func EnsureDirs() error {
	dirs := []func() (string, error){
		Root,
		BlobsDir,
		ManifestsDir,
	}

	for _, fn := range dirs {
		dir, err := fn()
		if err != nil {
			return err
		}
		if err := os.MkdirAll(dir, 0755); err != nil {
			return err
		}
	}
	return nil
}