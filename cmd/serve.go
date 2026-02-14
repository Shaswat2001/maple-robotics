package cmd

import (
	"fmt"
	"github.com/spf13/cobra"
)

var serveCmd = &cobra.Command{
	Use: "serve",
	Short: "Start the MAPLE server",
	Run: func(cmd *cobra.Command, args []string) {
		port, _ := cmd.Flags().GetInt("port")
		fmt.Printf("Starting MAPLE server on http://127.0.0.1:%d\n", port)
	},
}

func init() {
	serveCmd.Flags().IntP("port", "p", 11434, "port to listen on")
	rootCmd.AddCommand(serveCmd)
}