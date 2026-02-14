package cmd

import (
	"fmt"
	"github.com/spf13/cobra"
)

var pullCmd = &cobra.Command{
	Use: "pull",
	Short: "Pull a model or environment",
	Run: func(cmd *cobra.Command, args []string) {
		cmd.Help()
	},
}

var pullPolicyCmd = &cobra.Command{
	Use: "policy MODEL",
	Short: "Pull a policy model",
	Args: cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		model := args[0]
		fmt.Printf("Pulling Policy %s... \n", model)
	},
}

var pullEnvCmd = &cobra.Command{
	Use: "env MODEL",
	Short: "Pull a env model",
	Args: cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		model := args[0]
		fmt.Printf("Pulling Env %s... \n", model)
	},
}

func init() {
	pullCmd.AddCommand(pullPolicyCmd)
	pullCmd.AddCommand(pullEnvCmd)
	rootCmd.AddCommand(pullCmd)
}