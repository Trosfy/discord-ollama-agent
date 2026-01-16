# Kai AI Augmentation System - Transcript

**Video:** https://youtu.be/Le0DLrn7ta0
**Speakers:** Daniel (Unsupervised Learning) & Clint

---

So today we're going to cover basically
two things. Um so we're going to cover
at a high level how to think about
augmenting yourself with AI as well as
some tactical examples and demos from
some really cool stuff Daniel has built.
And then the second part is basically
open Q&A. So ask Daniel and I anything
you want. So just sort of open
discussion. Little bit about Daniel.
He's a longtime great friend of mine. So
I'm a huge fan of him as a person as
well as his work. He runs unsupervised
learning which is one of the biggest and
best security newsletters in my opinion.
He recently keynoted OASP global apps
USA which is pretty cool. He was
previously a security leader at Apple,
Robin Hood and other places but recently
the past couple of years he's been
focusing on AI so both applying it to
security where he does some consulting
work with companies as well as using AI
for human flourishing which is what
we're going to be uh focusing on a bit
today. And just a fun anecdote,
basically every week sometime between 10
PM and midnight, I get a text from
Daniel that's basically like, "Dude, I
just built the sickest thing ever." And
then he sends me a screenshot of some uh
cool new like dashboard or something
he's built. So today, we're going to be
covering a number of those things that
he's been building cuz he's constantly
tweaking and improving his stack. Yeah.
With a focus on using AI to augment
yourself. So that's a little bit of
context, but yeah, let's jump right into
it. Daniel, I pass it to you.

## Why I Built Kai

Awesome. Thanks, Clint. Appreciate the
intro and thanks for uh having me. I
appreciate the time here.

Appreciate it.

So want to talk about why I built Kai.
Some stuff you need to know before you
can build a similar system if you want
to do that. Core principles and
engineering that I put like into it like
the design concepts and everything. Many
of which are actually different than uh
cloud code natively. So the Kai system
is built on cloud code, but it's kind of
designed to be agnostic and not just
have the base stuff that's in cloud
code. I've extended it quite a bit.
We're going to do a deep dive on an
actual skill. We're going to do a quick
demo and I'm going to show you how to
get started on your own. And uh we got
an FAQ which uh you could take a picture
of. I don't think I'm going to read
through that one. And then as Clint
said, we have time for discussion and QA
afterwards. So like Clint also said, I
want to apologize beforehand because
this could be like an hour for each
section. And in fact, when I do it other
places, it is actually much longer. So
we will have to go pretty fast. But um
I'm going to go in more detail about a
lot of these things than I've done
anywhere else. So that should be fun to
uh get into. But the goal is ultimately
to give you enough detail and direction
to build your own system like this. So
why I made it in the first place? The
main reason is because I just wanted to
get better overall at everything that I
do. I don't like being surprised by
things. I like understanding how things
work. And when I'm surprised, that means
I didn't know how it worked at whatever
level. So that's basically like an AI
augmentation system was the first thing
I I thought about at the end of 22 when
this all went crazy. I also think
regular jobs are going away. I talk
about this postc corporate world and I'm
really worried about that for humans and
I think the best way to get ready for
that is to get really really good at
being a human and that means
understanding yourself and using AI to
magnify yourself.

## 5 Levels of AI Impact

So this is my model
for thinking about how AI is going to
impact like the job market and how much
it's going to I guess get inside of the
workflow of how we do work and
eventually take over more and more of
that. And I use this to sort of keep
pressure on myself kind of thinking
about where it's all going and basically
where am I and how ready am I and how
ready are other people as well. So it's
five levels. Before 2022, we didn't have
any AI, right? So we basically did all
this work ourselves. 23 to 25 roughly. I
mean, this is all general, right? This
is like the first level of AI. It's chat
bots. Everyone understands this. It's
like you ask a question, you get a thing
back, and then you could do manual work
with that thing, which is still really
valuable. And you notice at the bottom
here, we're inside of the section for
human- centered work. So the first three
sections here are largely human focused.
And what we're entering into now is like
this whole agentic thing, which by the
way, I hate the word agentic. I I think
it's a good word. I think it's a cool
word, but everything is agentic now. Got
aentic toaster ovens or or whatever.
It's uh it's being overused, but uh this
has been going on for a couple of years.
I I think it's starting now. Yeah, I
think it sort of started at the end of
24 a little bit and then they were like,
"Oh, 2025 is going to be the year of the
agent." Turns out that that was kind of
true. And that's this layer here, right?
That's level two. And the next two we
could talk about later if you want to
hit me up afterwards, but they're less
human focused in terms of how much of
the work is being done. And this system
that I'm going to show you is firmly
right here in the uh level two.

## Getting Started

So what
can you do to get started? So the most
important thing is understanding like
you can't just start building, right? A
lot of people try to just start building
random stuff inside of a system like
this and then they try a few things,
they don't really work that well and
they kind of abandon them. And I I
taught a course on this four times so
far and I always start with the same
thing, which is who are you? What do you
care about? What do you actually want to
get good at? And how can technology save
you time so you can actually do more of
the stuff you care about and less of the
stuff that's just like busy work. So for
me, this is roughly what mine looks
like. One through four is definitely
like the most important to me. Reading,
thinking, writing, and discussing
things. Five is what I've been spending
most of my time on, which is building.
This used to be known as coding, by the
way. I've stopped saying like when I
talk to Clint or whatever, what have you
been doing? Uh, coding, right? Cuz
that's what I was doing before, and now
it's like I'm actually thinking and
writing, which is producing the coding.
It's a weird abstraction. I also do a
lot of consulting for customers,
building a bunch of products. For
physical stuff, I play table tennis,
like the crazy kind where you're really
far away from the table. I play drums
and I'm getting into kickboxing. And
perhaps most importantly, I orient a lot
of my life around trying to help other
people do the same thing that I'm I'm
doing here, which is just self-discovery
and like self-magnification.

## Core Design Principles

So, the system itself and its design.
So, these are the principles that I
built Kai on top of and what sets it
apart from cloud code. Cloud code has
some of this naturally built in, but
I've kind of augmented it for the Kai
system to be a lot more of of these
things with a heavy focus on on these
principles. So, what we're going to do
is go one by one through these and talk
about them as a concept and show you
what it looks like inside the system.

### 1. Prompting is Still Crucial

So, they go roughly in order of
importance. And this is definitely the
most important one. Even though it's
kind of invisible, it it's become less
talked about. So basically, if you
remember back to early 24, I don't know,
maybe in 23 as well, it's it's hard to
actually remember because it flows
together, but a lot of companies were
talking about prompting. Oh, you got to
learn how to prompt. Prompt engineering
was the big word, right? Put out the
fabric project, which is a whole bunch
of crowdsourced prompts, and that was
just kind of the thing that you did. AI
was heavily associated with prompting.
And in my opinion, prompting never
became less important. In fact, I think
it's more important than ever now. I
think it's just more hidden because
there's lots of other shiny things that
people are talking about. The other
reason is because AI is doing a lot of
that prompting for us. The way I think
about this is clear thinking is
basically the center of everything and
clear thinking becomes clear writing and
then clear writing is essentially what
prompting is and that that becomes
really good AI. So a good heristic for
this is like can you explain this to
yourself especially to yourself like 6
months later when you might not have
remembered what you actually built. and
you explain it to others and if you
can't then AI really can't understand it
either right when the AI is confused
that's when everything goes sideways so
I think prompting is still like the most
important thing to AI cuz at the end of
the day it's all language it's all
instructions so it's all prompting so
what this actually means in practice is
I've spent many thousands of hours at
this point working on my whole structure
I don't know why this thing is 7 gigs I
actually took it down from 10 gigs but
that's a lot of text that's not actually
the scaffolding cuz that would be a
nightmare and nothing would be able to
parse it. So there's a lot of outputs
and other stuff, but the system is
definitely growing. And the most
important directories inside of here are
things like skills and hooks and
history, which we're going to talk
about.

### 2. Scaffolding > Model

So this leads really well into
the next one, which is the scaffolding
is more important in my opinion than the
model. Now, there's some exceptions to
this, and all the news, of course, is
about the new models when they get
released. you know, Gemini 3 recently,
Opus 4.5 recently, but I've always been
team scaffolding, and I I continue to be
team scaffolding. Obviously, it's it's
best to have both, right? If you have
really good models, it magnifies the
scaffolding, and if you have really good
scaffolding, it magnifies the models.
But if I had to choose between the
latest model with not very good
scaffolding or excellent scaffolding
with a model from 6 months ago or even a
year ago or even 18 months ago,
honestly, I would definitely pick the
ladder. And a quick quick note on this.
Yeah. So I totally agree with Daniel
about the scaffolding one thing. So I
spent a lot of time reading and thinking
about people who are using AI for
vulnerability detection for example like
analyzing source code or scanning
running systems and I think it's
difficult to say like a given model can
or can't do this because again to
Daniel's point like the scaffolding
around it makes such a huge impact like
if you see OpenAI's Arvar or deep sleep
or codemen from Google basically they
are giving all these sorts of tools and
orchestration layers like around the
models which allow them to perform
orders of magnitude better on like the
same task. So when someone says this
current model can or can't do something,
it's kind of actually hard to know that
for sure given just better orchestration
and context management and things like
that can cause meaningfully different
outcomes. So I think scaffolding is
huge. So yeah, that I think that's a key
point. So I just wanted to like
emphasize that. Okay. Yeah, back to you.

Yeah, I think those are all good points.
Another one is the AIXCC competition.
Trail of Bits really crushed it there.
They they did a lot of scaffolding
there. The Atlanta team as well. So good
examples of that. So uh my skills
directory is probably the most important
center of the scaffolding. Currently
have like 65 skills in here. A lot of
these are just very uh pointed at my own
stuff that not really useful to other
people, but a number of these are just
core and just essential to everything I
do.

### 3. Determinism (Code Before Prompts)

Next one of is the last of my three
central philosophies for the system. And
this one is to be as deterministic as
possible. Right? So what does that mean?
It means in practice basically code
before prompts is what that really turns
into. If I have anything that I can do
in code, I do it in code first. I don't
even use AI at all. And if you think
about it this way, Kai is more like a
tech orchestration system. Not really an
AI system cuz I had something kind of
similar before before even AI obviously
wasn't as good. But when you add AI on
top of it, it really magnifies it. But
it's more of an orchestration framework.
This is my art skill for example which
we're going to talk about more and the
tools directory within that skill and
this is just deterministic regular code
right anything that my art skill does is
actually running code at the end of it
right at the end of the day it's
actually just deterministic code and
that provides as much consistency and
control as possible and also has the
upside of not involving AI at all for
the step which saves a bunch of tokens
and usage and everything. This one I've
broken out just because it's so
important, but really it's the same
thing we just talked about. Code before
prompts. I'm not really sure what my
current percentage of this is, like 80
versus 20. I think I'd like I don't
know. Curious what you think, Clint,
what this balance should be like the
ideal balance, but I feel like it should
be mostly deterministic with like AI
wrapping it 8020. I don't know. I'll
have to do more thinking on that and see
how it plays out. Yeah, I was just going
to say I think if there's something that
can be done programmatically
deterministically, I think code is the
right solution for it because it's like
cheaper and you know you're going to get
the answer you expect. In the past
creating that code maybe has been time
or cost prohibitive but now with like
cloud code and other similar coding
agents like creating the deterministic
code can be done in a fraction of the
time. So yeah, I think it depends on the
domain. When you need like a fuzzy
answer that's sort of difficult to solve
generically completely
deterministically, then maybe sort of
some sort of prompt and code system is
better. But yeah, I think the core
intuition here is like if you can solve
it deterministically, like probably
that's the better solution and maybe you
vibe your way to like code that does it.
But yeah, trying to solve everything
with prompts, at least as of today, is
going to be inefficient, costly, and
like if you were like find all the
routes in this repo, you're going to
find a lot of them, but cloud code or
whatever system is going to miss some of
them. So, if you can do that with like
another tool that you know is going to
work, it's just better. But yeah, you
were saying about Anthropic.

Yeah, Anthropic came out with a thing
about this actually kind of throwing
shade at their own MCP. like they
invented MCP and they're like, "Hey, you
might want to actually just do this in
Typescript and use the MCP to get the
service that you want to use, turn that
into TypeScript and actually run that
instead cuz then you're not calling all
these uh tokens before and after. You're
just getting the results and then you
could use the results to give to AI."
So, I thought it was really cool and
within like a little while of them
releasing that, I upgraded a couple of
my MCPs to not use MCP anymore.

### 4. Specifications, Tests, and Evals

So this next one is specifications, tests and
evals. And this is also playing at the
whole concept of determinism and
consistency. So there's a big tendency
in AI to use vibes. This is just like a
gentic everything is vibes. Vibe
hacking. Now vibe marketing, of course,
vibe coding. Big thing Clint and I
actually talk about a lot is how do we
know any of this is working, right? How
do you actually test any of this stuff?
How do we actually get consistency from
what we build? This is the skill.mmd for
my development skill. And you can see
I'm starting with specd driven
development. And this is roughly based
off of GitHub's really excellent project
called spec kit. And I basically
simplified it because it was it was a
little bit too involved. But um first
you create specs, then you create plans,
then you write tests, then you write
code. And that's the flow that uh that
system uses. And I'm always optimizing
this, but this is the general flow that
I follow.

### 5. Unix Philosophy

So, the next one I've been
obsessed with since being in college in
like the 1990s. And uh shout out to my
buddy Kundi who uh showed me the command
line for the first time, which honestly
it might have been one of the best days
of my life when I found out I could pipe
the output of one command into the input
of the next. I mean, it truly tripped me
out. And I feel like I've been building
systems based on that concept ever
since. So the way it materializes inside
of this system is I try to have each
container do one thing well and I build
different skills to call each other
instead of replicating that
functionality inside of each one. I've
got a number of examples of this within
Kai. But this is a red team skill and
this red team can actually hit a network
architecture, an application
architecture, threat modeling. It could
do like all sorts of different stuff.
But I often use it to attack ideas that
I have to see like blind spots if I'm
missing something. But the red team
skill calls a first principal skill and
breaks that down further into other
pieces, right? So it works in a flow to
really break open ideas and attack the
ideas. This is another really cool
example which is called lifelog pulls
off of my uh necklace pendant which I'm
wearing right now. I I could show when I
turn on the camera. It's basically a
thing that I can turn on when I'm
walking and I could say, "Hey, new idea
or new blog or yeah, I should do a piece
of content on this or whatever." And
then I just talk and it captures it and
then when I get back I could say okay
that thing I just said when I was
walking take this and do that with it.
Right? So it goes and pulls the content
from the transcript, pulls out the
section, summarizes it from there. I
could do research on it. I could blog on
it. I could do whatever. I could red
team the idea for example and it's all
done using natural language prompt. Uh
just me talking to Kai and it cross
calls all those different ones. I also
want to mention real quick custom slash
commands. These are commands you could
just type forward slash include code to
run. And these are also calling one or
multiple. The cse one is calling create
story explanation which is a skill and
it's just another way to call into
skills as well worth mentioning. So if I
take a piece of content I want to get
information from like this is a great
article on tlddrc and this was from
Jason Chan who built this security
program at Netflix. So you could take
that and you could do like this for/cse5
which will give me five levels of
explanation of what this thing is about.
And this is what it does when it's
working. It actually uses fabric here
which I forgot about that but it uses
fabric switch u which goes actually uses
Gina AI to do this and it pulls down the
markdown for the thing and then it runs
the cse skill and it returns the results
in five levels. And cool little thing
for Kai is Kai also updates the tab name
inside of the Kitty terminal to be the
result and reads it in Kai's voice which
we'll see later.

### 6. Engineering/SWE Principles

Next one is engineering
or S sur principles which is also part
of this determinism story which I feel
like it's I might move that up to be
like the most important one. But my
background is hacking in like the
security sense, but also in the more
pure sense of like building and creating
and breaking things, right? So, I've
been a crappy programmer since the early
2000s, but I've never been an actual
software engineer, right? And there's a
huge difference, as anyone who's been
both knows, there's a huge difference
between an SWE and someone who programs.
So what I'm doing now is I'm learning a
lot of engineering stuff that I should
have learned in college and trying to
build that into the DNA of the system
which usually manifests as tests and
evals and stuff like that. The way it
mostly manifests is through like the
development skill where I'm going
through you know true tested engineering
practices of like building plans,
test-driven development and all that
sort of thing. This is a thing I talk to
Clint a lot about. Most people don't
know this because he never talks about
it, but Clint Loki is a PhD in computer
science, and it definitely shows when he
starts talking about tests and evals.
You will see him light up like a
Christmas tree. So, that's always fun.

For context, a lot of Daniel's skills
and prompts and things like that. Some
of them have like this detailed
backstory about maybe the person's
persona and their goals in life. And uh
I'm like, Daniel, does that does that
help? And he's like, you know, vibes,
baby. But then also like test them
rigorously in practice to make sure that
they work consistently.

Yeah. And I've got some examples of that
when we talk about the voice system. I
put all this effort into it and I'm
always wondering myself and then
especially when I talk to Clint, I'm
like, "Okay, what if I had this same
exact prompt without all this
personality stuff?" Yeah. So, we're
we're doing a bunch of eval stuff so we
can test this stuff at scale.

### 7. CLI-First Design

This one
is super cool. This is a relatively new
addition to the Kai system. So, not only
am I trying to write code for as much as
possible in the system, but I'm actually
trying to have that be executed via CLI
instead of just calling the code and
having the model try to figure out how
to actually run it. So, I love the
command line so much. Terminal is my
favorite place to live. And I love the
fact that there's documentation, there's
flags, there's switches, there's
options, right? And it means you know
how to use it. You know how to use a
command line by running the help
command. And you know who else loves
that? AI loves that. AI absolutely loves
when it doesn't have ambiguity in what
it's supposed to do. So, going all the
way back to the concept of clarity and
AI not being confused, like there's
nothing more clear than how to use a
command line tool, assuming it's well
documented. So, I've got a command line
tool for launching Kai. Actually, when I
type K, that used to just be a ZSH
alias, but now I've got a actual command
line tool for it. And the most useful
switches I I think are actually the uh
switch M switch to dynamically load
MCPS. And uh shout out to Indie Dev Dan
for this one. He's a bull developer
who's doing AI stuff on YouTube. You
should definitely check him out. He also
did this and I was like, "Oh, that's a
great idea." So I built the command line
to be able to do that. And here's the
actual command for generating images
using my art skill. So I can pass in a
model, but the default is actually nano
banana pro for obvious reasons. It's
just incredibly good. But I have all
these different options. And this is
what Kai actually uses to generate
images.

### 8. High-Level Flow

So this next one is a highle
flow for a concept that solidifies a lot
of what we've been talking about. It's
just a way of thinking about how to
organize the entire system. Basically,
you figure out what you want to do. You
figure out if you can do it in code.
Then if I can, I build a command line
tool around that. Then I use prompting
to run the command line tool. And then I
use skills or agents to call it or to
run it in parallel. And that's that's
kind of the flow and the structure. And
this is basically how all these skills
work is going from the top level goal
all the way down to the codebased
implementation.

### 9. Self-Updating System

This next one is super
fun. It is also super useful. Basically,
I have a whole bunch of capabilities
within Kai that are used to update Kai
himself, right? So it's like
self-update, self-healing,
self-improvement, and not just like a
little component or a module or
something, but like the system overall.
So you've seen all different components
of the scaffolding. We have skills, we
have workflows within the skills that
execute things. We have code in the
command line tools. Then we have the
models, right? We also have different
services that could be called via MCP or
API or whatever. So the best example of
this is I have an upgrade skill. I guess
that's a good name for it if it's doing
upgrades. So the upgrade skill, it's a
universal skill that multiple sources,
it hits multiple sources on the internet
and I'm looking at those sources because
they're constantly releasing stuff that
I cannot keep up with manually and I
don't want Kai to get behind. So when I
say run the upgrade skill, it will go
and find all these different sources.
It'll parse the latest content. It will
review all of Kai's documentation.
There's a single file that documents all
of Kai. So Kai will read that,
understand how he works, and then
understand all the updates that it just
pulled from different sources, and then
look for opportunities to improve. So
one of the sources it looks at is the
anthropic engineering blogs, all of
their releases on GitHub. I mean,
they're releasing stuff constantly, like
every day, multiple times during the
day. There's no way I could possibly
follow it all. I also do this for
YouTube channels. Somebody talks about a
new technique, automatically parse it
and bring it in. And security-wise, I do
it for security research as well. So
like all the talks that Clint puts out
when he puts out like, oh, here's the
latest videos from so and so conference
or whatever, I parse those and update my
testing methodology if there's like a
new technique. So here's an actual
example of me running this a little
while ago. So Anthropic had a release
saying how they could improve uh routing
within skills using this keyword use
when. and they basically emphasized,
hey, look, you need to be using this
because if you're not getting your
skills to function the way that you
want, they're not being triggered
properly, you need to make sure you have
this in the front matter. So Kai ran the
upgrade skill, found this, and came back
with this as the top recommendation. I
said, "Okay, do it." And within like 5
minutes, the entire Kai system was
upgraded with this uh piece of
functionality. And after that, skills
worked way better. So, as I was making
this like prepping for the conversation
here, I said look for in our history for
learnings because everything that I do
for an upgrade actually across the
system, it's all captured in the history
system and it's broken down into
structures which we'll actually see a
little bit later. But this basically
looked up our archive of things that
we've done to learn over time. And
that's exactly what it found. It found
this use win thing.

### 10. Custom Skill Management

All right. So, this
one is absolutely crucial. I should
probably raise it in priority as well.
custom skill management. So this is
probably the most significant thing that
I did on top of cloud code. It it's just
a completely different structure. So
skills are already really good inside of
cloud code. It's pretty good at routing
by itself, but what I did was add a
supplemental system that's more explicit
about the routing. And I'm getting like
I don't know 95 98%. I don't know the
actual number. Me and Clint will have to
figure out the actual number. We need uh
you know rigor around this thing. but
it's basically routing in the system
prompt which goes to a routing table of
workflows that go to specific prompts
and then within the directory there's
also a tools directory that the
workflows actually call and like we
talked about those are ideally
deterministic code as opposed to
prompts. So, what this does is it
produces way better results for being
able to do multiple things inside of a
category such as art. And I'm going to
show the art skill later, but what it
does is allows me to just speak in plain
language and get exactly pretty much
what I asked for.

### 11. Custom History System

Last couple here,
custom history system. We touched on
this one a little bit, but basically I
have sessions, learnings, research
decisions, all sorts of different
categories here. And when we get done
doing anything, if any agent does
anything, if I do it, if Kai does it, if
any sub agent does it, Kai thinks about
what we did, turns that into a summary
and writes it into this history system.
That's part of the reason I've got like
six gigs of stuff grown over time here.
But file system is cheap and file system
is fast. So I I like this way better
than rag for most things. This is what
the directory actually looks like. And
it basically allows me to understand
where we've been, where we are, and
where we're going, right? Cuz I hate
making the same mistake over and over. I
especially have a system like this for
bugs, calling out bugs that keep coming
up when I'm building web applications.
So I could say, capture a learning on
this, capture a learning on this, and
have that be crystallized into a thing
that Kai can then use to upgrade the
development skill. So we don't do that
anymore.

### 12. Voice System

And this last one is kind of
flourish to be honest, but it can be
useful as well. I basically have a fully
customized voice system for Kai and all
the different agents that we use within
it. So we've got architects, engineers,
researchers, QA testers, interns. They
all have different personalities. This
is the part that I'm not sure how much
this is actually helping, but it's fun.
And they all have different approaches
to their work, too, right? Some are like
library scientists, some are like super
curious, and they have different voice
characteristics based on their
personalities. So, what this means is
while the agents are talking to me or to
each other, you can actually hear
emotion in what they're talking about.
If they come back with a finding and
they're excited about it, like you can
actually hear that in the voice
rendition. I still need to do more evals
on this uh as I talked about. So, the
whole thing goes through a voice server,
which we have, which is part of the PI
system. It goes through 11 Labs API.

---

*Note: Transcript continues with more demos and Q&A discussion*
