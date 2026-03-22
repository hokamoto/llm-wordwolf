// Learn more about clients at https://docs.boundaryml.com/ref/baml/client-llm

client<llm> LLMInstance {
  provider "openai-generic"
  options {
    base_url "https://openrouter.ai/api/v1"
    api_key env.OPENROUTER_KEY
    model "openai/o4-mini"
    allowed_role_metadata ["cache_control"]
  }
}

// Self-hosted LLM

client<llm> LLMInstanceBackup {
   provider "openai-generic"
   options {
     base_url "http://localhost:8000/v1"
     api_key "EMPTY"
     model "openai/gpt-oss-20b"
     allowed_roles ["system", "developer", "assistant", "user"]
     default_role "user"
     temperature 1.0
     reasoning_effort medium
   }
 }

// https://docs.boundaryml.com/ref/llm-client-strategies/retry-policy
retry_policy Constant {
  max_retries 3
  strategy {
    type constant_delay
    delay_ms 200
  }
}

retry_policy Exponential {
  max_retries 2
  strategy {
    type exponential_backoff
    delay_ms 300
    multiplier 1.5
    max_delay_ms 10000
  }
}