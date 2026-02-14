package cmd

import (
	"fmt"
	"github.com/spf13/cobra"
)

var logsCmd = &cobra.Command{
	Use:   "logs [MODEL]",
	Short: "Show logs",
	Args:  cobra.MaximumNArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		follow, _ := cmd.Flags().GetBool("follow")
		
		if len(args) == 0 {
			fmt.Println("Showing server logs...")
		} else {
			fmt.Printf("Showing logs for %s...\n", args[0])
		}
		
		if follow {
			fmt.Println("(following)")
		}
	},
}

func init() {
	logsCmd.Flags().BoolP("follow", "f", false, "follow log output")
	rootCmd.AddCommand(logsCmd)
}