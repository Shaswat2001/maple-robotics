package cmd

import (
	"fmt"
	"github.com/spf13/cobra"
)

var rmCmd = &cobra.Command{
	Use: "rm",
	Aliases: []string{"remove"},
	Short: "Remove a model or environment",
	Run: func(cmd *cobra.Command, args []string) {
		cmd.Help()
	},
}

var rmEnvCmd = &cobra.Command{
	Use: "env ENV",
	Short: "Remove an environment",
	Args: cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		model := args[0]
		fmt.Printf("Removing Env %s... \n", model)
	},
}

var rmPolicyCmd = &cobra.Command{
	Use: "policy MODEL",
	Short: "Remove an policy",
	Args: cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		model := args[0]
		fmt.Printf("Removing Policy %s... \n", model)
	},
}

func init(){
	rmCmd.AddCommand(rmPolicyCmd)
	rmCmd.AddCommand(rmEnvCmd)
	rootCmd.AddCommand(rmCmd)
}