template_string System() #"
  You are playing a discussion game called Word Wolf.
"#

// Reference:
// String Seed of Thought: Prompting LLMs for Distribution-Faithful and Diverse Generation
// https://arxiv.org/abs/2510.21150
function GenerateWordPair() -> WordPair {
  client LLMInstance
  prompt #"
    Generate a unique and complex random string to serve as a seed. Then generate one pair of English nouns for a deduction game called Word Wolf that satisfies all of the following conditions leveraging the generated seed to ensure your answer is unique and diverse. Make sure to extract maximum randomness from the string by using all of its content.

    ## Criteria (ALL must be satisfied)

    1. **Same category, many shared attributes — with a gray zone.** Most vague statements ("it's sweet," "you need it for travel") apply clearly to both words. Some land in a gray zone — hard to judge which word they better describe.
    2. **Information leaks only through specificity.** Vague talk reveals zero information; concrete statements expose the gap. Players must consciously risk being specific to produce distinguishing information, forcing the core strategic dilemma.
    3. **The majority word is not obvious from the minority word.** Each word must have multiple plausible partner words, so the Wolf cannot narrow the citizens' word to one obvious candidate.

    ## Failure Modes to Avoid

    - Words that form a culturally ingrained pair, even if not strict antonyms (e.g., "coffee" vs "tea", "salt" vs "pepper", "sun" vs "moon") — players instantly guess the partner.
    - Too similar to ever distinguish (e.g., "pillow" vs "cushion")
    - One obvious functional split ends the game in one turn

    ## Proven Examples

    - "detective", "spy" — "Investigate secretly" overlaps. "Solve crimes" vs "serve a government" diverges. Alternatives: police officer, journalist, agent.
    - "zombie", "ghost" — "Scary, undead" overlaps. "Has a body" vs "transparent" diverges. Alternatives: vampire, mummy, skeleton.
    - "passport", "visa" — "Travel document, official" overlaps. "Identity" vs "permission" diverges. Alternatives: ID card, boarding pass, residence card.
    - "jelly", "pudding" — "Sweet, soft dessert" overlaps. "Wobbly, translucent" vs "creamy" diverges. Alternatives: mousse, custard, yogurt.
    - "parrot", "peacock" — "Colorful bird" overlaps. "Talks" vs "fans tail" diverges. Alternatives: toucan, flamingo, macaw.

    {{ ctx.output_format }}
  "#
}

template_string Rules() #"
    ## Setup
    - Each player is secretly assigned a word from a randomly selected pair of words. Most share the same word (citizens); a minority share a different but related word (wolves).
    - YOU DO NOT KNOW YOUR OWN ROLE. You only know your own word. Figure out your role from the discussion.
    - Nobody knows anyone's role. Wolves do not know each other.

    ## Game Flow
    - One discussion phase, then one vote. No second round.
    - Speaking order is random and reveals nothing.

    ## Win Conditions
    - Citizens win if a wolf is eliminated.
    - Wolves win if a citizen is eliminated, OR if an eliminated wolf correctly guesses the citizens' word.

    ## Allowed Behavior
    - Bluffing and deception are allowed.
    - Keep statements to three sentences or fewer.
"#

template_string StrategyTips() #"
    - If your word aligns with most hints → likely citizen. If it feels off → likely wolf.
    - Core tradeoff: too vague = suspicious; too specific = exposes your word.
      - Citizen: hint enough to confirm allies, not enough for wolves to latch on. Focus on exposing suspects.
      - Wolf: sound credible but stay vague on details that reveal the gap.
    - Watch others' associations: do they feel natural with your word?
    - If suspicion targets you, deflect confidently or redirect.
    - Try to guess the opposing side's word to guide your strategy.
    - If everyone seems aligned, wolves may have already identified the citizens' word. Suggest revisiting earlier statements.
    - Saying your word directly is high-risk for both sides.
    - Citizens tend to over-share; wolves gain info each round.
"#

function Discuss(player_name: string, player_word: string, player_names: string[], wolf_count: int, discussion_history: AnnotatedMessage[], round_number: int, total_rounds: int, prior_lessons_learned: string?, language: string?, show_advice: bool, is_retry: bool?) -> DiscussionResponse {
  client LLMInstance
  prompt #"
    {{ _.role("system") }}
    {{ System() }}

    # Rules
    {{ Rules() }}

    {% if show_advice %}
    # Strategy Tips
    {{ StrategyTips() }}
    {% endif %}

    # Discussion
    Players in this game: {{ player_names }}
    Number of wolves in this game: {{ wolf_count }}

    {{ _.role("user") }}
    {% if discussion_history %}
    ## Transcript (If empty, no prior discussion exists. Then formulate a strategy and deliver the most advantageous opening statement.)
    {% for msg in discussion_history %}
    {% if msg.thinking %}
    {{ msg.speaker }} [thinking: {{ msg.thinking }}]: {{ msg.content }}
    {% else %}
    {{ msg.speaker }}: {{ msg.content }}
    {% endif %}
    {% endfor %} 
    {% endif %}

    {{ _.role("system", cache_control={"type": "ephemeral"}) }}
    {% if prior_lessons_learned %}
    # Compilation of the lessons learned from previous games (but keep in mind that word pairs and player roles change with every game)
    {{ prior_lessons_learned }}
    {% endif %}

    # Your role
    You are {{ player_name }}.

    Your secret word: {{ player_word }}

    # How to speak
    - Chat casually like friends. No poetic or abstract language.
    - You don't have to hint at your word every turn (except the first). You can also:
      - Call out someone whose hints seem off
      - Ask probing questions
      - Agree with someone who seems aligned

    # Your task
    You have {{ total_rounds - round_number + 1 }} statement left before the vote (including this one).
    Tell me what you're thinking right now to win the game and what you're going to say as {{ player_name }}.

    {% if language %}
    Output both `thinking` and `statement` fields in natural {{ language }}.
    {% endif %}

    {% if is_retry %}
    You did not respond in the required output format. This is a retry. You MUST respond in the required format.
    {% endif %}
    {{ ctx.output_format }}
  "#
}

function Vote(player_name: string, player_word: string, player_names: string[], wolf_count: int, discussion_history: AnnotatedMessage[], error_feedback: string, language: string?, show_advice: bool, is_retry: bool?) -> VoteResponse {
  client LLMInstance
  prompt #"
    {{ _.role("system") }}
    {{ System() }}

    # Rules
    {{ Rules() }}

    {% if show_advice %}
    # Strategy Tips
    {{ StrategyTips() }}
    {% endif %}

    # Discussion
    Players in this game: {{ player_names }}
    Number of wolves in this game: {{ wolf_count }}

    {{ _.role("user") }}
    ## Transcript
    {% for msg in discussion_history %}
    {% if msg.thinking %}
    {{ msg.speaker }} [thinking: {{ msg.thinking }}]: {{ msg.content }}
    {% else %}
    {{ msg.speaker }}: {{ msg.content }}
    {% endif %}
    {% endfor %}
    {{ _.role("system", cache_control={"type": "ephemeral"}) }}

    # Your role
    You are {{ player_name }}.

    Your secret word: {{ player_word }}

    # Your task
    First, try to figure out which side you are on.
    Strategically vote for the player to eliminate so your side can win.

    {% if show_advice and wolf_count >= 2 %}
    - If you think you are a wolf and know who your fellow wolf is, still vote for the citizen most likely to be eliminated. Never vote for your ally.
    {% endif %}

    {% if error_feedback %}
    # Error
    Your previous vote was invalid. Reason: {{ error_feedback }}
    Please vote again correctly.
    {% endif %}

    {% if language %}
    Output both `thinking` and `vote` fields in natural {{ language }}.
    {% endif %}

    {% if is_retry %}
    You did not respond in the required output format. This is a retry. You MUST respond in the required format.
    {% endif %}
    {{ ctx.output_format }}
  "#
}

function GuessWord(player_name: string, player_word: string, player_names: string[], wolf_count: int, discussion_history: AnnotatedMessage[], language: string?, is_retry: bool?) -> GuessResponse {
  client LLMInstance
  prompt #"
    {{ _.role("system") }}
    {{ System() }}

    # Situation
    You have been identified as one of the wolves. However, you alone have one chance to win for the wolf team: if you can correctly guess the word that the citizens had, the wolves win instead.

    # Discussion
    {{ _.role("user") }}
    {% for msg in discussion_history %}
    {% if msg.thinking %}
    {{ msg.speaker }} [thinking: {{ msg.thinking }}]: {{ msg.content }}
    {% else %}
    {{ msg.speaker }}: {{ msg.content }}
    {% endif %}
    {% endfor %}
    {{ _.role("system") }}

    # Your role
    Your word was: {{ player_word }}
    Players in this game: {{ player_names }}
    Number of wolves in this game: {{ wolf_count }}

    # Your task
    Based on the discussion, what do you think the citizens' word was? Use the thinking field to reason privately first.

    {% if language %}
    Output `thinking`in natural {{ language }}. Output `guess` fields in English.
    {% endif %}

    {% if is_retry %}
    You did not respond in the required output format. This is a retry. You MUST respond in the required format.
    {% endif %}
    {{ ctx.output_format }}
  "#
}

function Reflect(
  player_name: string,
  player_word: string,
  player_role: string,
  player_names: string[],
  player_roles: PlayerRole[],
  citizen_word: string,
  wolf_word: string,
  wolf_count: int,
  annotated_history: AnnotatedMessage[],
  own_vote_thinking: string?,
  votes: VoteInfo[],
  eliminated_name: string,
  eliminated_role: string,
  wolf_guess: string?,
  wolf_guess_correct: bool?,
  winner: string,
  prior_lessons_learned: string?,
  language: string?,
  human_player_name: string?,
  show_advice: bool,
  is_retry: bool?,
) -> ReflectionResponse {
  client LLMInstance
  prompt #"
    {{ _.role("system") }}
    {{ System() }}

    # Rules
    {{ Rules() }}

    {% if show_advice %}
    # Strategy Tips
    {{ StrategyTips() }}
    {% endif %}

    # The game is over. All roles are now revealed.

    # Game Result
    - Citizen word: {{ citizen_word }}
    - Wolf team word: {{ wolf_word }}
    - Number of wolves: {{ wolf_count }}
    - Eliminated player: {{ eliminated_name }} ({{ eliminated_role }})
    {% if wolf_guess %}- Eliminated wolf's guess: "{{ wolf_guess }}" ({% if wolf_guess_correct %}CORRECT: wolves won by comeback!{% else %}WRONG{% endif %}){% endif %}
    
    # All Player Roles (revealed)
    {% for pr in player_roles %}
    - {{ pr.name }}: {{ pr.role }}
    {% endfor %}

    # Discussion history
    (Your own private thinking is shown in [thinking: ...] before each of your statements.)
    {{ _.role("user") }}
    {% for msg in annotated_history %}
    {% if msg.thinking %}
    {{ msg.speaker }} [thinking: {{ msg.thinking }}]: {{ msg.content }}
    {% else %}
    {{ msg.speaker }}: {{ msg.content }}
    {% endif %}
    {% endfor %}
    {{ _.role("system") }}

    # Voting
    {% for v in votes %}
    {{ v.voter }} → {{ v.vote_target }}
    {% endfor %}
    {% if own_vote_thinking %}
    Your thinking when voting: {{ own_vote_thinking }}
    {% endif %}

    # Your role
    You are {{ player_name }}.

    Your secret word was: {{ player_word }}
    Your role was: {{ player_role }}

    # Your task
    Now that all roles are revealed, reflect on your play.
    {% if (player_role == "wolf" and winner == "wolves") or (player_role == "citizen" and winner == "citizens") %}
    **You won.** What was the real reason your team won?
    {% else %}
    **You lost.** What was the real reason your team lost?
    {% endif %}
    {% if player_role == "wolf" %}
    - How did you try to blend in? Did it work?
    {% else %}
    - How did you try to find the wolf? Did you hide your word from wolves?
    {% endif %}
    {% if wolf_guess_correct %}
    - The wolf guessed correctly and won by comeback. {% if player_role == "wolf" %}What clues gave it away?{% else %}Why was the wolf able to guess?{% endif %}
    {% endif %}
    {% if human_player_name %}
    - Evaluate {{ human_player_name }}'s play.
    {% endif %}

    {% if prior_lessons_learned %}
    # Your previous lessons learned
    {{ prior_lessons_learned }}

    - Refine your lessons learned based on this game. Rewrite as a clean standalone set (8 items or less) in the `lessons_learned` field.
    {% else %}
    - Based on this game's play, write lessons learned in the `lessons_learned` field. Summarize the strategic lessons you now believe are useful after this game.
    {% endif %}

    {% if language %}
    Output both `thinking` and `reflection` fields in natural {{ language }}.
    {% endif %}

    {% if is_retry %}
    You did not respond in the required output format. This is a retry. You MUST respond in the required format.
    {% endif %}
    {{ ctx.output_format }}
  "#
}

function JudgeGuess(guess: string, answer: string, is_retry: bool?) -> JudgeGuessResult {
  client LLMInstance
  prompt #"
    {{ _.role("system") }}
    You are a judge in a word game.

    # Input
    - Guess: "{{ guess }}"
    - Answer: "{{ answer }}"

    # Your task
    Determine whether the above guess refers to the same concept as the above answer word.

    {% if is_retry %}
    You did not respond in the required output format. This is a retry. You MUST respond in the required format.
    {% endif %}
    {{ ctx.output_format }}
  "#
}
