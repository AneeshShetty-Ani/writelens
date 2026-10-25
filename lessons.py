"""Short lessons behind each suggestion ("Why?"), with a before and after, so the writer learns the rule
instead of only fixing the sentence."""

# card title -> (why it matters, before, after)
LESSONS = {
    "Spelling": ("Typos make readers doubt the care behind the rest of the work, even when the ideas are good.",
                 "We recieved the results.", "We received the results."),
    "Passive voice": ("The passive hides who did the action and adds words. Readers follow “who did what” "
                      "most easily.", "The survey was analysed by the team.", "The team analysed the survey."),
    "Informal words": ("Casual words suit speech and messages; in essays they make an argument sound less "
                       "careful.", "A lot of students are gonna struggle.", "Many students will struggle."),
    "Talking to the reader": ("Essays usually discuss ideas, not the reader. “You” can sound like a "
                              "conversation or an instruction.", "If you study late, you remember less.",
                              "Students who study late remember less."),
    "Repeated sentence starts": ("The same opening word again and again makes writing sound like a list and "
                                 "hides how ideas connect.", "The test was hard. The class was tired. The marks fell.",
                                 "The test was hard, and with a tired class, marks fell."),
    "Wordy phrase": ("Every extra word is something the reader has to process. Short forms say the same thing "
                     "faster.", "Due to the fact that it rained, we left.", "Because it rained, we left."),
    "Cliché": ("Overused phrases are skimmed past and sound unoriginal. A specific statement is more "
               "convincing.", "Last but not least, the cost matters.", "Finally, the cost matters."),
    "Mixed UK/US spelling": ("Switching between two spelling systems looks like a mistake. Pick one and use it "
                             "throughout.", "We analysed the color.", "We analysed the colour."),
    "Sentence variety": ("Sentences of the same length create a flat rhythm. A short sentence after long ones "
                         "adds emphasis.", "It rained all day. We stayed in all day. We read books all day.",
                         "It rained all day, so we stayed in with our books. Nobody minded."),
    "Long sentence": ("Long sentences make readers hold many ideas at once. Splitting them makes each point "
                      "land.", "The plan, which was approved in May after a long debate that included every "
                      "department, failed.", "The plan was approved in May after a long debate. It failed."),
    "Filler adverbs": ("Words like “very” and “really” add emphasis without meaning. A stronger word does "
                       "the job.", "It was very big and really important.", "It was huge and essential."),
    "Weak verbs": ("General verbs (make, get, do) say little. A specific verb carries more meaning in one "
                   "word.", "We made a decision to get better results.", "We decided to improve the results."),
    "Repeated words": ("Using the same word over and over tires the reader. Vary it, or use a pronoun.",
                       "The meeting helped the meeting organisers plan the meeting.",
                       "The meeting helped its organisers plan the next one."),
    "Contractions": ("Formal writing usually spells words out; contractions sound conversational.",
                     "The results don't show a link.", "The results do not show a link."),
    "Weak opening": ("Readers decide in the first lines whether to keep reading. Generic openings delay your "
                     "point.", "In today's world, technology is everywhere.",
                     "Smartphones now shape how students revise."),
    "Conclusion": ("A conclusion should pull the points together and say why they matter, without new "
                   "evidence or copying the introduction.", "In conclusion, as I said, social media is popular.",
                   "Social media helps students connect, but only with limits on screen time."),
}
