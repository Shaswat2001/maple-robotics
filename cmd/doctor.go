package cmd

import (
	"fmt"
	"github.com/spf13/cobra"
)

var doctorCmd = &cobra.Command{
	Use:   "doctor",
	Short: "Check system health",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Println("Checking system health...")
		fmt.Println("[ ] Docker")
		fmt.Println("[ ] GPU")
		fmt.Println("[ ] Disk space")
		fmt.Println("[ ] Network")
	},
}

func init() {
	rootCmd.AddCommand(doctorCmd)
}