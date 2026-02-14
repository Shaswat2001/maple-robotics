package cmd

import (
	"fmt"
	"github.com/spf13/cobra"
)

var showCmd = &cobra.Command{
	Use:   "show MODEL",
	Short: "Show model information",
	Args:  cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		model := args[0]
		fmt.Printf("Model: %s\n", model)
		fmt.Println("Architecture: ")
		fmt.Println("Parameters: ")
		fmt.Println("Size: ")
		fmt.Println("Environments: ")
	},
}

func init() {
	rootCmd.AddCommand(showCmd)
}