package cmd

import (
	"fmt"
	"github.com/spf13/cobra"
)

var listCmd = &cobra.Command{
	Use:     "list",
	Aliases: []string{"ls"},
	Short:   "List downloaded models and environments",
	Run: func(cmd *cobra.Command, args []string) {
		// List both by default
		fmt.Println("POLICIES:")
		fmt.Println("NAME\t\t\tSIZE\t\tMODIFIED")
		fmt.Println()
		fmt.Println("ENVIRONMENTS:")
		fmt.Println("NAME\t\t\tSIZE\t\tMODIFIED")
	},
}

var listPolicyCmd = &cobra.Command{
	Use:   "policy",
	Short: "List downloaded policies",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Println("NAME\t\t\tSIZE\t\tMODIFIED")
	},
}

var listEnvCmd = &cobra.Command{
	Use:   "env",
	Short: "List downloaded environments",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Println("NAME\t\t\tSIZE\t\tMODIFIED")
	},
}

func init() {
	listCmd.AddCommand(listPolicyCmd)
	listCmd.AddCommand(listEnvCmd)
	rootCmd.AddCommand(listCmd)
}