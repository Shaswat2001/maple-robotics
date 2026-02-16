package server

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os/exec"
	"strings"
	"time"
)

// Docker images for each model architecture
var modelImages = map[string]string{
	"openvla": "maplerobotics/openvla:latest",
	"smolvla": "maplerobotics/smolvla:latest",
	"groot":   "maplerobotics/groot:latest",
	"octo":    "maplerobotics/octo:latest",
	"openpi":  "maplerobotics/openpi:latest",
}

// Runtime manages a policy container
type Runtime struct {
	containerID   string
	containerName string
	port          int
	modelName     string
	running       bool
}

// NewRuntime creates a new runtime manager
func NewRuntime(port int) *Runtime {
	return &Runtime{
		port: port,
	}
}

// Start starts a model container
func (r *Runtime) Start(architecture, modelPath, name, device string) error {
	if r.running {
		r.Stop()
	}

	image, ok := modelImages[architecture]
	if !ok {
		return fmt.Errorf("unknown architecture: %s", architecture)
	}

	// Sanitize name for Docker (replace : with -)
	safeName := strings.ReplaceAll(name, ":", "-")
	r.containerName = fmt.Sprintf("maple-%s-%d", safeName, time.Now().Unix())

	// Build docker run args
	args := []string{"run", "-d",
		"--name", r.containerName,
		"-p", fmt.Sprintf("%d:8000", r.port),
		"-v", fmt.Sprintf("%s:/model:ro", modelPath),
		"-e", "MODEL_PATH=/model",
	}

	// Add GPU flag only if not CPU
	if device != "cpu" {
		args = append(args, "--gpus", "all")
	}

	args = append(args, image)

	// Start container
	cmd := exec.Command("docker", args...)

	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("failed to start container: %s", string(out))
	}

	r.containerID = string(bytes.TrimSpace(out))
	r.modelName = name
	r.running = true

	// Wait for container to be ready
	return r.waitReady()
}

// Stop stops the container
func (r *Runtime) Stop() error {
	if !r.running {
		return nil
	}

	exec.Command("docker", "stop", r.containerName).Run()
	exec.Command("docker", "rm", r.containerName).Run()

	r.running = false
	r.containerID = ""
	r.containerName = ""
	r.modelName = ""
	return nil
}

// Act sends an inference request
func (r *Runtime) Act(image, instruction string) ([]float64, error) {
	if !r.running {
		return nil, fmt.Errorf("runtime not running")
	}

	payload := map[string]string{
		"image":       image,
		"instruction": instruction,
	}

	data, _ := json.Marshal(payload)
	resp, err := http.Post(
		fmt.Sprintf("http://127.0.0.1:%d/act", r.port),
		"application/json",
		bytes.NewReader(data),
	)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result struct {
		Action []float64 `json:"action"`
		Error  string    `json:"error"`
	}
	json.NewDecoder(resp.Body).Decode(&result)

	if result.Error != "" {
		return nil, fmt.Errorf(result.Error)
	}

	return result.Action, nil
}

// IsRunning returns whether runtime is running
func (r *Runtime) IsRunning() bool {
	return r.running
}

// ModelName returns current model name
func (r *Runtime) ModelName() string {
	return r.modelName
}

func (r *Runtime) waitReady() error {
	url := fmt.Sprintf("http://127.0.0.1:%d/health", r.port)

	for i := 0; i < 60; i++ {
		resp, err := http.Get(url)
		if err == nil && resp.StatusCode == http.StatusOK {
			resp.Body.Close()
			return nil
		}
		time.Sleep(time.Second)
	}

	return fmt.Errorf("container failed to start")
}