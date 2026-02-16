package cmd

import (
	"fmt"
	"os"

	"github.com/maple-robotics/maple/registry"
	"github.com/maple-robotics/maple/storage"
	"github.com/spf13/cobra"
)

var pullCmd = &cobra.Command{
	Use:   "pull",
	Short: "Pull a model or environment",
	Run: func(cmd *cobra.Command, args []string) {
		cmd.Help()
	},
}

var pullPolicyCmd = &cobra.Command{
	Use:   "policy MODEL",
	Short: "Pull a policy model",
	Args:  cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		model := args[0]

		// Ensure storage directories exist
		if err := storage.EnsureDirs(); err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			os.Exit(1)
		}

		// Pull from registry
		reg := registry.New()
		lastStatus := ""
		err := reg.Pull(model, func(status string, completed, total int64) {
			if status == "downloading" && total > 0 {
				pct := float64(completed) / float64(total) * 100
				fmt.Printf("\r  %-50s %6.1f%%", lastStatus, pct)
				if completed == total {
					fmt.Println(" done")
				}
			} else if status != "downloading" {
				lastStatus = status
				fmt.Printf("%s\n", status)
			}
		})

		if err != nil {
			fmt.Fprintf(os.Stderr, "\nError: %v\n", err)
			os.Exit(1)
		}

		fmt.Printf("Successfully pulled %s\n", model)
	},
}

var pullEnvCmd = &cobra.Command{
	Use:   "env ENV",
	Short: "Pull an environment",
	Args:  cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		env := args[0]
		fmt.Printf("Pulling environment %s...\n", env)
		// TODO: implement env pulling
	},
}

func init() {
	pullCmd.AddCommand(pullPolicyCmd)
	pullCmd.AddCommand(pullEnvCmd)
	rootCmd.AddCommand(pullCmd)
}
