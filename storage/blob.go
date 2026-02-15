package storage

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

// BlobPath returns the path for a given digest
func BlobPath(digest string) (string, error) {

	dir, err := BlobsDir()
	if err != nil {
		return "", err
	}
	// Normalize: sha256:abc -> sha256-abc
	name := strings.Replace(digest, ":", "-", 1)
	return filepath.Join(dir, name), nil
}

// BlobExists check if blob exists
func BlobExists(digest string) (bool, error) {

	path, err := BlobPath(digest)
	if err != nil {
		return false, err
	}
	_, err = os.Stat(path)
	if os.IsNotExist(err) {
		return false, nil
	}

	return err == nil, err
}

// BlobSize returns the size of a blob
func BlobSize(digest string) (int64, error) {
	path, err := BlobPath(digest)
	if err != nil {
		return 0, err
	}
	info, err := os.Stat(path)
	if err != nil {
		return 0, err
	}
	return info.Size(), nil
}

// OpenBlob opens a blob for reading
func OpenBlob(digest string) (*os.File, error) {
	path, err := BlobPath(digest)
	if err != nil {
		return nil, err
	}
	return os.Open(path)
}

// WriteBlob writes data and returns its digest
func WriteBlob(r io.Reader) (string, int64, error) {
	dir, err := BlobsDir()
	if err != nil {
		return "", 0, err
	}

	tmp, err := os.CreateTemp(dir, "tmp-")
	if err != nil {
		return "", 0, err
	}
	tmpPath := tmp.Name()
	defer os.Remove(tmpPath)

	hasher := sha256.New()
	writer := io.MultiWriter(tmp, hasher)

	size, err := io.Copy(writer, r)
	if err != nil {
		tmp.Close()
		return "", 0, err
	}
	tmp.Close()

	// Compute digest and move to final path
	digest := fmt.Sprintf("sha256-%s", hex.EncodeToString(hasher.Sum(nil)))
	finalPath := filepath.Join(dir, digest)

	if err := os.Rename(tmpPath, finalPath); err != nil {
		return "", 0, err
	}

	return digest, size, nil
}

// DeleteBlob removes a blob
func DeleteBlob(digest string) error {
	path, err := BlobPath(digest)
	if err != nil {
		return err
	}
	return os.Remove(path)
}

// ListBlobs returns all blob digests
func ListBlobs() ([]string, error) {
	dir, err := BlobsDir()
	if err != nil {
		return nil, err
	}

	entries, err := os.ReadDir(dir)
	if err != nil {
		if os.IsNotExist(err) {
			return []string{}, nil
		}
		return nil, err
	}

	var digests []string
	for _, e := range entries {
		if !e.IsDir() && strings.HasPrefix(e.Name(), "sha256-") {
			digests = append(digests, e.Name())
		}
	}
	return digests, nil
}
