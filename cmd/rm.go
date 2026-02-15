package cmd

import (
	"fmt"
	"os"

	"github.com/maple-robotics/maple/storage"
	"github.com/spf13/cobra"
)

var rmCmd = &cobra.Command{
	Use:     "rm",
	Aliases: []string{"remove"},
	Short:   "Remove a model or environment",
	Run: func(cmd *cobra.Command, args []string) {
		cmd.Help()
	},
}

var rmPolicyCmd = &cobra.Command{
	Use:   "policy MODEL",
	Short: "Remove a policy model",
	Args:  cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		ref := args[0]
		name, tag := storage.ParseModelRef(ref)

		// Check if exists
		exists, err := storage.ManifestExists(name, tag)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			os.Exit(1)
		}
		if !exists {
			fmt.Fprintf(os.Stderr, "Error: model %s not found\n", ref)
			os.Exit(1)
		}

		// Load manifest to get blob digests
		m, err := storage.LoadManifest(name, tag)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			os.Exit(1)
		}

		// Collect all digests from this manifest
		digests := []string{m.Config.Digest}
		for _, l := range m.Layers {
			digests = append(digests, l.Digest)
		}

		// Delete manifest first
		if err := storage.DeleteManifest(name, tag); err != nil {
			fmt.Fprintf(os.Stderr, "Error deleting manifest: %v\n", err)
			os.Exit(1)
		}

		// Check which blobs are still referenced by other manifests
		allRefs, _ := storage.ListManifests()
		referenced := make(map[string]bool)

		for _, otherRef := range allRefs {
			otherName, otherTag := storage.ParseModelRef(otherRef)
			if otherM, err := storage.LoadManifest(otherName, otherTag); err == nil {
				referenced[otherM.Config.Digest] = true
				for _, l := range otherM.Layers {
					referenced[l.Digest] = true
				}
			}
		}

		// Delete unreferenced blobs
		deleted := 0
		for _, d := range digests {
			if !referenced[d] {
				if err := storage.DeleteBlob(d); err == nil {
					deleted++
				}
			}
		}

		fmt.Printf("Deleted %s (%d blobs removed)\n", ref, deleted)
	},
}

var rmEnvCmd = &cobra.Command{
	Use:   "env ENV",
	Short: "Remove an environment",
	Args:  cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		env := args[0]
		fmt.Printf("Removing environment %s...\n", env)
		// TODO: implement env removal
	},
}

func init() {
	rmCmd.AddCommand(rmPolicyCmd)
	rmCmd.AddCommand(rmEnvCmd)
	rootCmd.AddCommand(rmCmd)
}
