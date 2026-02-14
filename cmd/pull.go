package cmd

import (
	"fmt"
	"github.com/spf13/cobra"
)

var PullCmd = &cobra.Command{
	Use: "pull MODEL",
	Short: "Pull a model from the registry",
	Args: cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		model := args[0]
		fmt.Printf("Pulling %s... \n", model)
	}
}

func init() {
	rootCmd.AddCommand(pullCmd)
}