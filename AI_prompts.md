# Vibe Coder Prompts

Problem 1 — log of prompts typed to the AI coding assistant (Claude Code), in order.

---

## Prompt 1 — Set up workspace

> Uh, let's store everything. that I'm about to do in this folder HW5, all right? Uh, and now let me yeah, I'm going to do a lot of stuff. So let's start from there. Can you confirm?

## Prompt 2 — Copy the database

> first of all, as I'm laying a foundation please make a copy of the database file, which name is data/campus_customs_new.db

## Prompt 3 — Project context

> So I'm going to give you a context of this problem. So um, there, there's multi-agent operations called campus customs. And it's a agentic team that runs the shop. It opens tickets, uh, land on a board, we have customer order, we have rent, we have unpaid bills, discount requests, whatever the shop has to handle. And our job is to build three pieces that talk to each other. The first one is an MCP server. The second one is a fast API backend. with a multi-agent team. And the third pieces of it is the React dashboard. So a human can watch the agent at work and approve requests. Uh, we're gonna, I'm gonna give you more guideline and what we're trying to do here is we're gonna build some agent first, the boss who reads each ticket and decide who should work on it and make final calls. The second one is inventory. Um, it will check stock by SKU and size. Spot shortfalls, uh, a figures out which vendor can restock. Accounting uh, watches cash and invoices, check margins and prepare payments or purchase orders for human approval. Uh, the, next one is facilities. Uh, handles the shop space side, lease, uh, rent, etc. The last piece is about customer service, which drafts messages for customers. All right. Can you please confirm you uh, understand all of that?

## Prompt 4 — Business rules

> How are we going to set up some rules? So for example, desk.date_tody this field is today for the shop. Use this date to determine what is overdue. And vendor lead time come from the vendors table. Uh, a vendor will not ship new product while they still have an open unpaid invoice. Human approval is only required for any payments. Points will be deducted if this is not done. If payment is made, make sure to update the relevant table. If there's not enough cash, the pay tool must refuse. No negative balance, please. And cash only goes out in this scenario. Also, before a full run to resolve the tickets, make sure to reset the database to the original values. Please do not email customer or call real vendors. Uh, please just have the drafts stay on the board. Can you please confirm?

## Prompt 5 — Start this prompt log

> Please create AI_prompts .md Right now, and keep it updated as we work. This file will be the log of what I typed to you. This is for problem one. and the title is Vibe Coder Prompts.

## Prompt 6 — Problem 2: study the database

> Now, we are on problem two. Study the campus custom database. Open data/campus_customs.db

## Prompt 7 — Reset DB, study tickets, start harness.md (first attempt, interrupted)

> I'll be the original file to data/campus_customs_new.db. Also, study the three open tickets. So we know how they link to other tables. Additionally, please start output/harness.md for each table list the fields and one short line on why table matters for the agent.

## Prompt 8 — Reset DB, study tickets, start harness.md (corrected)

> Copy the original file to data/campus_customs_new.db. Also, study the three open tickets. So we know how they link to other tables. Additionally, please start output/harness.md for each table list the fields and one short line on why table matters for the agent.

## Prompt 9 — Problem 3: build the MCP server

> We're at problem three. Build the MCP server.
> Please create  a MCP server in mcp_server/ using FastMCP. It should talk to data/campus_customs_new.db. No need to connect or run it right now. I want to make sure every agent in this entire scenario entire uh, practice will use the tool in this MCP server specifically I'm gonna add more tools to the server later but for now please write three tools that we absolutely need for the tickets in the database please keep the name clear and Do not invent any data out of thin air. Please only use information in the database. Additionally, please list All three MCP tools in output/harness.md. for each tool, I want to see which table it reads. Which tickets it helped unlock? One hundred one, one hundred two, or one hundred three? And one sentence, on why the tool is the right one for that ticket. And I want to point out that please don't give me a line such as, reads inventory. Those are not specific. Please tie the tool to the ticket. Last but not least, please add a short mcp_server/README.md file that explains what the MCP server is for and which database file it uses. And the three tools it has. Go.

## Prompt 10 — Problem 4: connect the MCP server and test each tool

> All right, now we're on problem four: add the MCP server to vibe coder and test each tool. Please add the MCP server to this project specifically. So we can call the tools from, from here. Please save the connection JSON text in .mcp.json at the project root.

## Prompt 11 — Problem 4: smoke-test evidence

> Okay, let's continue on problem four. I want you to test each of the three MCP tools. Please save the evidence in output/mcp_smoke/json. For every tool issue include the prompt that you asked the um, the vibe coder. The tool name. The tool output. Which must match value in data/campus_customs_new.db the um, the vibe coder, the tool name, the tool output, which must match values in

## Prompt 12 — Problem 5: build the agent team and grow the MCP tools

> Now we're on problem five. which is called build the agent team and grow the MCP tools. What we're going to do here is that we're going to build the agentic team for campus custom using pedantic AI. Which include boss inventory accounting facility and customer service. Please include prompts models and agent loops so they can delegate work to each other with full connectivity. Please put the agent prompts in backend/ prompts/. Please make sure to only have one file per agent. Put data types in backend/models.py and the agent files under backend/. Please only use Haiku 5.5 for every agent. Please also make sure to write each prompt in your own words with the sharp rules that agent needs. On the other hand, a more detailed prompts cover all aspects of an agent work and scope, score higher than a short, generic prompt. Additionally, before you connect the backend or wire the backend, please make sure to write down what you expect the team to do on each open ticket. Build output/desk_tickets.html This should be a page that you can double click with one tap per ticket. For example, 101, 102, or 103. Also add empty cache and reflection tabs for um, over upcoming problems. Leave them blank for now. On each ticket tab, fill the expected section only. This way we'll leave room for an actual section that you will fill after you run the agents.

## Prompt 13 — Problem 6: plan the three tickets

> Very cool. Now we're tackling um, problem six. which is called plan the three tickets. So before we wire the back end, please write down what do we expect the team to do on each open ticket. Build output/desk_tickets.html It's going to be a page where we can double check with one tab per ticket. Also add empty um, cache and an empty reflection tabs for later problems. Please leave them blank for now. On each ticket tab, fill and expected section. Only and please leave the room for an actual section you will fill after you run the agents. For each ticket's is expected section, write in your own words who the boss should call first and why. All the agent delegation you expect Of course, not the boss calls everyone. Um, which MCP tools you expect that run to use. Any plan that send every specialist on every ticket score low. We will compare this plan to waht actually happens when our agents resovle the three tickets

## Prompt 14 — Problem 7: backend routes

> Wonderful. Now we're on to problem seven. which is called backend routes. Our React front-end dashboard needs a backend it can call. We'll work on the front-end in the next problem. But in the backend, in backend/main.py, use FastAPI and Add routes that do the following. First, return the three tickets and whether each is open or resolved. Second, take a ticket ID and run your agent team on that ticket. Third, return recent agent events. What each agent said, and which tools they used. So the board can refresh. Next, approve a payment or purchase after a human clicks approve. And for more information, uh, agent only prepare the pay and this route is what actually changes cash. Next, return the current checking balance from cash_accounts Finally, reset the database to the original values when you want to try a fresh run.
>
> From the backend/ folder start the server with "uvicorn main:app --reload --port 8000" This will turn on our backend at "http://localhost:8000" so the front end dashboard can tell those routes. in "output/haress.md" list each route in one line (what URL/what it does)

## Prompt 15 — Problem 8: agent dashboard

> Okay, now we're on problem eight. Which is called agent dashboard. So please build the front end dashboard in frontend/ with react + vite + typescript. the page. Should call the routes that we built in problem seven. At minimum, the board should include the following. First, list all three tickets. Second, let you pick one ticket and start the agent team on it. Third, show each agent and what they're saying. Slash doing well the ticket runs. Fourth, mark a ticket resolved. when the run finishes. Next, show a short summary of what each ticket did. On that ticket, after that, let a human approve a pay or purchase when asked. Finally, show the checking balance if it should drop after an approved pay. Please make sure the dashboard looks very good I wanted to be uh, a very futuristic dashboard, um, it's the background should look like the um, the galactic city from the Star Wars, uh, where you have a lot of car flying around, uh, in motion, but also uh, you have a lot of skyscrapers, uh, and Yeah, there are a lot of stars, like behind you know, it's like a Star Wars. Capital theme. Aside from that, please tell the front end to talk to our back end at http://localhost:8000. On the back end, allow the Vite page origin (usualy http://localhost:5173) so the browser is allowed to call those routes. Start the board with "npm run dev"
>
> This opens the react desk in our browser, so we can pick tickets and watch agents. Please create "output/design.md" with what you chose for the dashboard look, basically lay out how agent read differently, how resolve tickets and cash show up and why. Uh, make it feel like, like, a, um, make it kind of sort of like Star Wars themed where it has the style of 3D pinball for windows: space cadet

## Prompt 16 — Question about the API key toast

> [screenshot of the toast "ANTHROPIC_API_KEY is not set; the agents can't run."] why this happens whenever I select one of the tasks?

## Prompt 17 — Switch models to gpt-6-luna via Portkey

> I don't have api key for claude, however i do have Portkey for APIkey. In this case can we swtich to gpt-6-luna for every agent? my port api key is "[REDACTED — stored only in the local .env file]" please don't share this online or with anyone else and keep it just locally

## Prompt 18 — Pinball sounds for the agents

> can you make the front end make the laser sounds and other sound similar to space cadet pinball game among different agents whenever they are working?

## Prompt 19 — Problem 9: resolve the tickets

> Now we're on problem nine, resolve the tickets. So before testing the agent on a full run over the three tickets, please reset the work database. data/campus_customs_new.db Again, so you start clean. Please note the starting checking balance, then run all three tickets on the board. For instance, 101, 103, and 102. Until each is. resolved. Please also open output/esk_tickets.html from Probelm 6. On each ticket tab, fill the actual section from this run. And show which agents worked, what they delegated, and which tools they used. Please keep our expected section so we can compare the two. Additionally, on the cache tab of the same "output/desk_tickets.html" Itemize the money. With the following. Starting checking balance after the reset. For each ticket, please explain how cash changed when that ticket is resolved. And why you should pay slash purchase dollar amount Also, show the, the ending checking balance. Itca must match cash_accounts in the working database. Wrong cache math lost points. Even if the board shows every ticket resolved. Also save output/resolved_tickets.json This is for each ticket ID. Final status short outcome what each agent contributed. And any human approval. ASide from that output/resolved_board.html This will be a page where we can double click with a screenshot of our React board for each resolved ticket, 101, 103, and 102. Append real runs to output/audit_trail.json. Finish output/harness.md So it covers table MCP tools, the five agents, API routes, the dashboard, and the safety rules.

## Prompt 20 — Problem 11: submit to GitHub

> Now we're moving on to problem 11. which is submit to GitHub. I need you to push the code to a public GitHub repository. So um, people can clone it. Um, and please also put it in output/github_url.txt. Do not push our real .env to the Github rep. Do includeboth database file under data/ (both the original and our working copy), which is submit to GitHub. I need you to push the code to a public GitHub repository so um, people can clone it. Um, and please also put it in. Readme should explain Copy original DB to the working copy when you need a clean run. Star MCP server start fast API backend start the React board reset the DB before a full three ticket run. Also, I have no idea how to push my code to a public GitHub. I have an account, but I'm not really sure how to push it. Online to the repository.

## Prompt 21 — Confirm the submission URL

> [screenshot of the assignment's "Website URL" field filled with https://github.com/Snowmanflame/campus-customs] so this is it right ?

## Prompt 22 — Submit without the final log update

> it's okay I'll submit now without the update

## Prompt 23 — Check the folder structure

> [screenshot of the expected hw5/ folder tree] can you confirm that our HW5 file following this similar structure?

## Prompt 24 — Add top-level requirements.txt and push

> please add it and push. This is for a different session.
