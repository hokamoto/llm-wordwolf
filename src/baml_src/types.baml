class DiscussionResponse {
  thinking string @description("Your private reasoning before speaking in the specified language (default: English). This is hidden from all other players, write freely. At most 5 sentences.")
  statement string @description("Your spoken message visible to all players in the specified language (default: English).")
}

class VoteResponse {
  thinking string @description("Your private reasoning before voting in the specified language (default: English). This is hidden from all other players — write freely. At most 5 sentences.")
  vote string @description("The exact name of the player you vote to eliminate. Must match one of the player names listed in the prompt exactly as written.")
}

class GuessResponse {
  thinking string @description("Your private reasoning in the specified language (default: English). Use this to work out what word the citizens had, based on the discussion. At most 5 sentences.")
  guess string @description("Your guess for the word that the citizens (not wolves) were given. This is your one chance to win for the wolf team. Output in English.")
}

class JudgeGuessResult {
  is_correct bool @description("True if the guess and the answer refer to the same concept (allowing minor variations). False if they are clearly different concepts.")
}

class VoteInfo {
  voter string
  vote_target string
}

class PlayerRole {
  name string
  role string @description("citizen or wolf")
}

class AnnotatedMessage {
  speaker string
  thinking string? @description("Private thinking shown only to you, not to other players. Only present for your own turns.")
  content string
}

class ReflectionResponse {
  reflection string @description("Your honest reflection on your own play in this specific game in the specified language (default: English). Be specific — reference actual moments from the discussion or voting.")
  lessons_learned string @description("Only output when prompted. How well the Strategy Tips were applied, and how you would improve them. Output in the specified language (default: English)")
}

class WordPair {
  random_seed string @description("Generated random seed")
  thinking string @description("Thinking about generating a word pair using the random seed.")
  word1 string
  word2 string
  competing_candidates string? @description("2+ alternative words that prevent unique guessing. Competing candidates must be distinct words, not modified forms of the original (e.g., for \"library,\" valid candidates are \"bookstore, archive, museum\" — not \"public library, school library, digital library\").")
}
