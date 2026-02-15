package cmd

import (
	"fmt"
	"os"

	"github.com/maple-robotics/maple/server"
	"github.com/maple-robotics/maple/storage"
	"github.com/spf13/cobra"
)

var serveCmd = &cobra.Command{
	Use:   "serve",
	Short: "Start the MAPLE server",
	Run: func(cmd *cobra.Command, args []string) {
		port, _ := cmd.Flags().GetInt("port")

		// Ensure storage directories exist
		if err := storage.EnsureDirs(); err != nil {
			fmt.Fprintf(os.Stderr, "Error creating directories: %v\n", err)
			os.Exit(1)
		}

		// Start server (blocks until error)
		s := server.New(port)
		err := s.Start()
		if err != nil {
			fmt.Fprintf(os.Stderr, "Server error: %v\n", err)
			os.Exit(1)
		}
	},
}

func init() {
	serveCmd.Flags().IntP("port", "p", 11434, "port to listen on")
	rootCmd.AddCommand(serveCmd)
}
