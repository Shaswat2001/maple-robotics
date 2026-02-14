package cmd

import (
	"fmt"
	"github.com/spf13/cobra"
)

var stopCmd = &cobra.Command{
	Use:   "stop [MODEL]",
	Short: "Stop a running model or the server",
	Args:  cobra.MaximumNArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		if len(args) == 0 {
			fmt.Println("Stopping MAPLE server...")
		} else {
			fmt.Printf("Stopping %s...\n", args[0])
		}
	},
}

func init() {
	rootCmd.AddCommand(stopCmd)
}