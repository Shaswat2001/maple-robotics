package cmd

import (
	"fmt"
	"github.com/spf13/cobra"
)

car RunCmd = &cobra.Command{
	Use: "run MODEL ENV",
	Short: "Run a model and environment"
	Args: cobra.ExactArgs(2),
	Run: func(cmd *cobra.Command, args []string) {
		model := args[0]
		env := args[1]

		task, _ := cmd.Flags().GetString("task")

		fmt.Printf("Model: %s\n", model)
		fmt.Printf("Environment: %s\n", env)
		if task != "" {
			fmt.Printf("Task: %s\n", task)
		}
	},
}

func init(){
	runCmd.Flags().StringP("task", "t", "", "task specification")
	rootCmd.AddCommand(runCmd)
}