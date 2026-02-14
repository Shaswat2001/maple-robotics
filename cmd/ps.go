package cmd

import (
	"fmt"
	"github.com/spf13/cobra"
)

var psCmd = &cobra.Command{
	Use: "ps",
	Short: "List running models or environments",
	Run: func(cmd *cobra.Command, args []string) {
		cmd.Help()
	},
}

var psEnvCmd = &cobra.Command{
	Use: "env",
	Short: "List running environments",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Println("NAME\t\t\tSTATUS\t\tPORT")
	},
}

var psPolicyCmd = &cobra.Command{
	Use: "policy",
	Short: "List running models",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Println("NAME\t\t\tSTATUS\t\tPORT")
	},
}

func init(){
	psCmd.AddCommand(psPolicyCmd)
	psCmd.AddCommand(psEnvCmd)
	rootCmd.AddCommand(psCmd)
}