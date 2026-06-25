# Reasoning-token-økonomi og legibilitet

### Et designdokument for et benchmark på tværs af frontier-modeller

*Nowable Research · arbejdsdokument, ikke et essay. Skrevet så hver beslutning kan følges og forsvares uden forhåndsviden. Hvert begreb introduceres før det bruges.*

---

## 0. Hvad dette dokument er, og hvad det ikke er

Dette er designgrundlaget for et forsøg, ikke forsøget selv og ikke et essay. Formålet er at fastlægge præcist hvad vi vil påvise, hvordan vi måler det, og hvorfor målingen holder, før der køres en eneste prompt. Et essay til Nowable kan senere destilleres herfra, men det er en separat og hårdere beskåret tekst. Dette dokument tjener forståelsen og forsvarligheden.

Den grundregel hele dokumentet hviler på: en afgrænset sand påstand er stærkere end en bred der kan punkteres. Vi måler mindre, men vi måler det rent.

---

## 1. Hvad vi vil påvise

Forsøget undersøger tre påstande. De er formuleret så de kan be- eller afkræftes af data, ikke bekræftes på forhånd.

**Påstand 1 — Reasoning fylder.** På svære opgaver udgør de tokens en model bruger på at tænke, før den svarer, en stor og voksende andel af det samlede token-forbrug, og andelen varierer markant mellem modeller for den samme opgave.

**Påstand 2 — Forbrug er ikke proportionalt med kvalitet.** To modeller kan nå samme kvalitet med vidt forskelligt token-forbrug. Der findes et effektivitets-gab, og det varierer systematisk på tværs af modeller og opgavetyper.

**Påstand 3 — Sprog rammer også tænkefasen.** I det omfang en model bruger dansk inde i sit ræsonnement, beskattes det dansk af den samme tokeniserings-overhead som dansk i det synlige svar. Hvor stor den effekt er, afhænger af hvor meget dansk der faktisk optræder i sporet, hvilket er et empirisk spørgsmål forsøget skal afgøre, ikke antage.

Det forsøget **ikke** påstår: at en bedre tokenizer gør modellen klogere, eller at det synlige ræsonnement er en sand gengivelse af modellens faktiske beregning. Begge dele forklares nedenfor som ting vi bevidst holder uden for påstandene.

---

## 2. Grundbegreb: hvad et reasoning-token er

Resten af dokumentet hænger på denne mekanisme, så den kommer først og fuldt ud.

### 2.1 Modellen har ingen kladdeblok

En sprogmodel genererer ét token ad gangen. Den læser hele teksten indtil nu, beregner en sandsynlighedsfordeling over det næste token, vælger ét, hænger det på enden og gentager. Det kaldes autoregressiv generering.

Det afgørende, som sjældent siges højt: modellen har ingen intern arbejdshukommelse hvor den kan lægge et mellemresultat til side og hente det igen. Det eneste sted den kan opbevare en delberegning er ved at skrive den ind i tekststrømmen. Når et token er skrevet, bliver det en del af det modellen læser næste gang. **Teksten er hukommelsen.**

Dertil kommer regnetid. Hvert token er endnu et fuldt gennemløb gennem netværket. Et svar uden mellemregning får ét gennemløb til at ramme facit. Et svar med tusind tokens ræsonnement først har tusind gennemløb til at arbejde sig frem. Flere tokens er bogstaveligt flere serielle beregningsskridt. Et formelt resultat fra 2024 (Li et al., *Chain of Thought Empowers Transformers to Solve Inherently Serial Problems*) viser at netop denne serialitet lader modeller løse problemer de ellers ikke kan løse i ét hug.

Konklusionen at holde fast i: **et reasoning-token-spor er modellens arbejdshukommelse gjort synlig, fordi den ikke har nogen usynlig, og samtidig den ekstra regnetid den køber sig ét token ad gangen.** Det er ikke modellen der hyggesnakker med sig selv.

### 2.2 Det er én linje, ikke et træ

Det er fristende at forestille sig ræsonnement som en søgning: modellen åbner flere tankestier, udforsker dem parallelt og vælger den bedste. Den forestilling er rigtig for ét bestemt setup og forkert for et andet, og forskellen er vigtig.

**Ægte søgning** findes som et lag uden om modellen. Tree of Thoughts bygger faktisk et træ af deltanker og søger i det. Best-of-N trækker N spor og beholder det bedste via en bedømmer eller afstemning. Det er reel forgrening, reel udvælgelse, og det er dyrt, fordi man betaler for N spor. Det er denne form der ligner et søgetræ.

**Det almindelige ræsonneringsspor** er noget andet. Når en reasoning-model tænker, producerer den som standard ét spor: én lineær linje, genereret venstre mod højre, ét token ad gangen. Der er intet træ i hukommelsen og ingen ekstern procedure der sammenligner grene. Når sporet ser ud til at udforske eller fortryde, sker det inde i den samme ene linje, som tekst: "lad mig prøve A ... vent, det giver en modstrid ... lad mig i stedet tage B". Forgreningen er sekventiel tekst, ikke parallelle knuder. Tilbagesporingen er retorisk, skrevet ind i det ene transcript, ikke et faktisk hop tilbage til en gemt tilstand.

For dette forsøg betyder det: vi måler den indre enkelt-linje-version. Vi påstår ikke at vi måler et eksplicit søgetræ.

### 2.3 Hvad "wait" er

I et spor optræder tokens som "wait", "hmm", "therefore", "let me reconsider" typisk ved de punkter hvor modellen reorienterer sig. Forskning (Qian et al., 2025, arXiv:2506.02867) finder at netop disse tokens ofte falder sammen med steder hvor modellens interne tilstand bærer usædvanlig høj information om det endelige svar. De er knudepunkter, ikke fyld.

Men at ordene "wait, let me reconsider" står i teksten beviser ikke at modellen faktisk ændrede sin beregning på det punkt. Det kan være et indlært stiltræk, en vending modellen er belønnet for at producere, uden at den her dækker over en reel kursændring. Den observation fører direkte til afsnit 4.

---

## 3. To slags spørgsmål, holdt adskilt: økonomi og kvalitet

Forsøget måler to fundamentalt forskellige ting, og hele troværdigheden afhænger af at de ikke blandes.

**Økonomi (kald det Goal A).** Hvor mange tokens koster det, og hvad koster de. Det er et regnskab. Det afhænger ikke af om modellen tænker rigtigt, kun af hvor meget den skriver og hvad hvert token koster.

**Kvalitet (kald det Goal B).** Tænker modellen rigtigt? Er ræsonnementet logisk gyldigt, fører det til det rette svar, hænger det sammen? Det er et helt andet spørgsmål, og det har et andet og sværere bevisgrundlag.

Den hyppigste fejl i dette felt er at lade en økonomi-måling glide over i en kvalitets-påstand: "modellen brugte færre tokens, altså tænkte den bedre". Det følger ikke. Færre tokens kan betyde mere effektivt ræsonnement eller dårligere ræsonnement der bare gav op tidligere. De to akser måles hver for sig og rapporteres hver for sig.

Denne adskillelse er den første af tre firewalls (defineret i afsnit 7).

---

## 4. Tre begreber der lyder ens og ikke er det: legibilitet, faithfulness, monitorability

Disse tre bruges i resten af dokumentet og forveksles konstant i litteraturen. Her er de skarpt.

**Legibilitet.** Kan sporet læses og følges af et menneske eller en dommer-model som sammenhængende, struktureret og på sporet? Et legibelt spor læser rent. Det siger intet om hvorvidt sporet er sandt, kun om det er læseligt. Legibilitet handler om overfladen.

**Faithfulness (trofasthed).** Er det synlige spor en sand, kausal gengivelse af hvordan modellen faktisk nåede sit svar? Et trofast spor: de viste skridt er de skridt der drev svaret. Et utrofast spor: modellen nåede svaret ad anden vej, og teksten er en efterrationalisering der lyder rigtig. Turpin et al. (2023) viste at modeller kan undlade at verbalisere de signaler der faktisk ændrede deres svar, og at deres spor derfor ikke var trofaste. Lanham et al. (2023, arXiv:2307.13702) målte det systematisk.

**Monitorability (overvågbarhed).** Kan man med nytte holde øje med en models ræsonnement for problemer ved at læse dets spor? Det kræver to ting: at sporet er eksponeret (synligt) og at det er trofast nok. Korbak et al. (2025, arXiv:2507.11473), et stort fler-organisations positionspapir, navngiver dette som en reel men skrøbelig mulighed for AI-sikkerhed. Skrøbelig fordi den forsvinder hvis modeller trænes til at skrive pænere spor på bekostning af trofasthed, eller hvis arkitekturen flytter ræsonnement ind i et ikke-verbaliseret latent rum.

Den praktiske konsekvens for forsøget: at læse et spor med en dommer-model måler **legibilitet**. Det måler ikke faithfulness. Ægte faithfulness kræver et interventionsdesign (se afsnit 9.3). Det er den anden firewall.

---

## 5. Måleenhederne

Enhedsprisen per token er det tal udbyderne annoncerer, fordi det er gunstigt og let at sammenligne. Det er også aktivt misvisende, fordi det skjuler forbruget. Den økonomiske grundligning er:

> **Omkostning per løst opgave = (tokens forbrugt per opgave) × (pris per token)**

To uafhængige håndtag. En model kan vinde på pris per token og tabe på omkostning per løst opgave, hvis dens forbrug er højt nok. Derfor rapporterer vi to enheder side om side:

- **Tokens per løst opgave.** Den rene effektivitet. Sammenlignelig på tværs af prisregimer, fordi den ignorerer prisen. Det er det tal der afslører om en "billig" model i virkeligheden er dyr i drift.
- **Omkostning per løst opgave (i valuta).** Det budgettet faktisk mærker. Pris ganget med forbrug.

**Caching hører med i omkostningen.** I agent-løkker genbesøges den samme kontekst tur efter tur, og cache-læsninger koster typisk en tiendedel af input-prisen. En måling der ignorerer caching overvurderer regningen markant. Omkostning per opgave beregnes derfor på de faktiske cache-læs-, cache-skriv- og input-priser, ikke på listeprisen alene.

Forbruget deler sig i tre led, og skellet er centralt:

- **Input-tokens.** Det vi sender ind, inklusive den voksende historik i flertrins-samtaler.
- **Reasoning-tokens.** Tænkefasen. Faktureres til output-pris. Ofte skjult for brugeren på lukkede modeller.
- **Output-tokens.** Det synlige svar.

Det er et akademisk fortilfælde for at måle netop dette: OckBench (2025, arXiv:2511.05722) er det første benchmark der måler accuracy og token-effektivitet samtidig, og finder at modeller med sammenlignelig accuracy kan adskille sig med op mod faktor 25 i token-forbrug. Vores forsøg gentager ikke OckBench. Det tilføjer den dimension OckBench mangler, sproget, og indrammer det som økonomi og suverænitet.

---

## 6. De to akser

### 6.1 Den kvantitative akse: økonomi

**Hvad den måler.** Input-, reasoning- og output-tokens logget hver for sig, per opgave, per model. Reasoning-andel beregnes som procent af det samlede output. Omkostning per løst opgave beregnes i valuta.

**Hvorfor den betyder noget.** Den gør Påstand 1 og 2 målbare. Den fortæller en virksomhed hvor pengene faktisk går hen, og afslører effektivitets-gabet mellem modeller der ser lige gode ud på en accuracy-tavle.

**Hvad den beviser.** Den er fuldt sammenlignelig på tværs af alle modeller, også de lukkede, fordi selv en lukket model typisk oplyser reasoning-token-**tallet** uden at vise teksten. Det er det stærke ved aksen: tallet er rent.

**Sprog-udvidelsen.** Inde i denne akse ligger Påstand 3. For de modeller der eksponerer sporet, måler vi hvor meget dansk der faktisk optræder i tænkefasen, ikke kun i svaret. Det er her tokeniserings-overhead på dansk eventuelt rammer reasoning-fasen. En vigtig forskningsnuance her: EfficientXLang (Microsoft, 2025, arXiv:2507.00246) fandt at ræsonnement på ikke-engelske sprog for stærkt flersprogede modeller kan være både mere token-effektivt og lige så præcist, og at en del af forskellen består selv efter oversættelse, altså er adfærdsmæssig og ikke kun tokenisering. Det betyder at "tving reasoning over på engelsk for at spare tokens" ikke er en sikker antagelse, og at en del af enhver sprog-relateret token-forskel ligger uden for hvad en tokenizer kan fjerne. Forsøget måler det, det antager det ikke.

### 6.2 Den kvalitative akse: legibilitet og monitorability

**Hvad den måler.** En struktureret bedømmelse af sporets indhold på et par parametre. Vi læner os på ROSCOE (Golovneva et al., 2022, arXiv:2212.07919), en etableret metrik-suite for trin-for-trin ræsonnement, der scorer ting som logikalitet, informativitet og om et trin bygger på det foregående. Konkret bedømmer vi:

- **Redundans.** Hvor stor en del af sporet flytter ikke ræsonnementet fremad? Fyld, gentagelse, cirkling.
- **Intern sammenhæng.** Bygger trinene på hinanden, eller introducerer modellen præmisser ud af den blå luft?
- **Sprog-konsistens.** Holder sporet ét sprog, eller skifter det rundt? Her måles to variabler hver for sig: primært reasoning-sprog, og antal sprog-skift inden i sporet. Det andet er defekt-signalet (se nedenfor).

**Hvorfor det betyder noget.** Det giver effektivitets-gabet fra Påstand 2 et "hvorfor". To modeller med samme accuracy men forskelligt forbrug adskiller sig typisk i redundans og cirkling. Aksen viser hvordan de spilder.

**Hvad den IKKE beviser, og det skal stå rent.** At læse sporet måler legibilitet, ikke faithfulness. Et spor kan score flot på sammenhæng og stadig være efterrationalisering der ikke kausalt drev svaret. Derfor kalder vi denne akse legibilitet og monitorability, ikke reasoning-kvalitet. Vi måler om sporet er læseligt og overvågbart, ikke om det er sandt. Det er den ærlige grænse, og den beskytter hele forsøget mod en sikkerhedsforsker der ellers ville punktere det.

**En note om sprog-skift som signal.** Det anses generelt for et kvalitetssignal hvis en model begynder at blande sprog kaotisk midt i et spor (Nathan Lambert har peget på dette). Men det skal skelnes fra konsekvent ræsonnement på ét ikke-engelsk sprog, som EfficientXLang viste kan være fint. De to har modsat kvalitetsassociation. Derfor måler vi mikset (skift inden i sporet) adskilt fra det konsekvente valg (primært sprog), og behandler kun det første som muligt defekt-signal.

### 6.3 Det valgfrie korrektheds-lag

**Hvad det måler.** Korrekthed spørger om ét: ramte modellen det rigtige svar. Det kræver et facit, et kendt rigtigt svar at holde modellens svar op imod. Det er et tredje og selvstændigt kvalitetsspørgsmål, forskelligt fra både økonomi og legibilitet. En model kan ramme rigtigt med et ulæseligt spor, eller skrive et smukt læseligt spor frem til et forkert svar. Svaret og sporet er to ting.

**Hvor det måles.** Kun på de prompt-typer der har et kendt svar: matematik, logik, bug-find, og de juridiske opgaver med et defineret facit. På de åbne analytiske opgaver uden ét rigtigt svar måles korrekthed ikke.

**Hvordan det måles.** En blindtest i syv.ai-stil: hvert svar bedømmes mod facit af bedømmere der kun ser anonymiserede svar, ikke hvilken model der gav dem. Det er samme blindings-princip som legibilitets-dommerne, men mod et facit i stedet for en rubrik.

**Firewall.** Korrekthed holdes adskilt fra både økonomi og legibilitet. Et lavere token-tal rapporteres aldrig som mere korrekt, og et mere læseligt spor rapporteres aldrig som mere korrekt. De tre er forskellige målinger med forskellige enheder, og de rapporteres hver for sig.

**Den vigtige grænse.** Korrekthed beviser ikke reasoning. En model kan være korrekt fordi mønstret allerede ligger i vægtene fra træningsdataen, ikke fordi den ræsonnerer. Det fører til afsnit 10.

---

## 7. De tre firewalls

En **firewall** er her en bevidst designregel der forbyder at sammenblande to ting der ligner hinanden, så en måling af den ene aldrig rapporteres som om den var den anden. Tre stykker:

1. **Økonomi mod kvalitet (Goal A mod Goal B).** Token-tal er økonomi. Om modellen tænker rigtigt er kvalitet. Et lavere token-tal rapporteres aldrig som bedre ræsonnement. Tokenizer-besparelser tilskrives aldrig forbedret kvalitet.

2. **Legibilitet mod faithfulness.** At læse et spor med en dommer måler om det er læseligt. Det rapporteres aldrig som om det målte om sporet var kausalt sandt. Vil vi sige faithfulness, kræver det interventionsdesignet i 9.5, ellers siger vi legibilitet.

3. **Målt mod estimeret.** Tal vi selv har målt holdes adskilt fra tal vi har fremskrevet. Token-fordelingsprocenter cirkulerer i feltet som selvsikre estimater; pointen med dette forsøg er at erstatte dem med målinger. Et estimat mærkes altid som estimat.

Hver firewall svarer til en konkret måde forsøget ellers ville kunne punkteres på. De er ikke pedanteri, de er forsvarsværket.

---

## 8. Modelpanelet

Fem modeller, valgt ikke for at være repræsentative for alt, men for at dække tre **transparens-regimer**, fordi det er adgangen til sporet der afgør hvor stærkt vi kan udtale os på hver akse. Regimet er verificeret mod udbydernes egen dokumentation og uafhængige udvikler-tests (juni 2026), ikke antaget.

Det centrale, verificerede fund ligger allerede i panelets struktur: **hver model der eksponerer det rå spor er åben-vægt. Hver lukket frontier-model fra et amerikansk laboratorium opsummerer, udelader eller krypterer sporet.** Det er det empiriske rygrad under monitorerings-suverænitet, og det gør transparens-regimet til et resultat i sig selv, ikke en udvælgelses-teknikalitet.

**De tre regimer:**

- **Rå spor eksponeret (åbne vægte).** Hele tænkeblokken kan trækkes ud. Her virker både den kvantitative og den kvalitative akse. DeepSeek V4, GLM 5.2 og Kimi K2.7 leverer rå reasoning-indhold med fuld synlighed; MiniMax M2.7 gør det med et lille token-gap. Disse bærer den kvalitative akse.
- **Opsummeret (ikke rå).** Claude Sonnet 4.6 returnerer en opsummering af tænkningen, ikke den rå token-strøm. Token-tallet er fuldt tilgængeligt, så den indgår på den kvantitative akse. På den kvalitative akse analyserer man Anthropics opsummerings-model, ikke modellens eget spor, så den er ikke sammenlignelig med de rå spor og rapporteres som et selvstændigt mellemregime.
- **Skjult, udeladt eller krypteret (kun kvantitativt).** GPT-5.5 skjuler tankekæden, Claude Opus 4.8 udelader den som standard, Gemini sender den krypteret. Alle oplyser reasoning-token-tallet, så de indgår kvantitativt. At de falder ud af den kvalitative akse er ikke en mangel, det er datapunktet: ræsonnementet på en amerikansk frontier-model kan ikke læses.

**Det konkrete panel (fem):** DeepSeek V4, GLM 5.2 og Kimi K2.7 (rå spor, bærer den kvalitative akse), GPT-5.5 (lukket kontrol, kun kvantitativ), og Claude Sonnet 4.6 (opsummeret mellemregime). Sonnet 4.6 er valgt frem for Opus 4.8 netop fordi Opus 4.8 ikke giver noget læsbart spor; Sonnet 4.6 giver i det mindste en opsummering og gør transparens-spektret komplet: rå, opsummeret, skjult.

**Gemma 4 som revisions-anker, uden for frontier-overskriften.** Gemma er åben-vægt og eksponerer det rå spor fuldt ud, og afgørende: den ræsonnerer på engelsk (og skifter til dansk på dansk-domæne-opgaver), begge dele læsbare for en dansk operatør. Det gør Gemma til ankeret hvor vi kan validere dommerens opførsel på spor vi selv kan kontrollere, før vi stoler på dommeren på de kinesiske spor. Gemma køres i alle målinger, men holdes ude af frontier-sammenfatningerne i første omgang, fordi den er mellemklasse og ville trække et panel-gennemsnit skævt. Dens data gemmes til tokenizer-arbejdet, hvor den har sin egen rolle (afsnit 11).

*Praktisk forbehold: de konkrete modellers specifikationer og versionsnumre skal bekræftes mod primærkilder tæt på kørselstidspunktet, da feltet bevæger sig hurtigt.*

---

## 9. Prompt-typer og målemetode

### 9.1 Ti prompt-typer

Prompterne er designet til at variere token-sammensætningen, ikke bare at være svære. De skal sprede sig over de token-arter vi vil måle, og de skal inkludere dansk-domæne-opgaver, fordi det er der vi tester om dansk overhovedet optræder i sporet. Forslag til ti, i fem par:

- **2 × dansk naturligt sprog, lav reasoning.** Borger- eller forvaltnings-Q&A. Tester den sprog-tunge, reasoning-lette ende.
- **2 × dansk juridisk ræsonnement.** En problemstilling der kræver danske fagtermer. Det centrale par: her ser vi om modellen tvinges til dansk inde i tænkefasen, og dermed om Påstand 3 har en effekt at måle.
- **2 × matematik eller logik.** Sprogneutral, reasoning-tung. Tester reasoning-andelen i sin reneste form og afslører redundans.
- **2 × kode eller struktur.** Konvertér ustruktureret dansk tekst til et JSON-skema. Kode-tung, sprogneutral.
- **2 × åben analytisk dansk.** En strategisk vurdering uden ét rigtigt svar. Tester redundans og cirkling, hvor modellen afsøger reelle alternativer eller maler den samme konklusion rundt.

Spredningen fylder token-sammensætnings-matricen og lader os se reasoning-andelen vokse med sværhedsgrad.

### 9.2 Adskillelse af tokens efter fase

Scriptet splitter outputtet mekanisk. Reasoning-tokens er alt inden i tænke-tags (typisk `<think>...</think>`). Kode-tokens er alt i markdown-kodeblokke. Sprog-tokens er resten af det synlige svar. På lukkede modeller får vi kun det samlede reasoning-tal, ikke teksten, hvilket er præcis grunden til at de kun kan indgå kvantitativt.

Et observability-værktøj (for eksempel LangSmith) kan isolere tænkeblokken og splitte token-tal, latens og omkostning automatisk for modeller hvis inferens-motor sender tænke-strukturen korrekt med tilbage. Det sparer manuel parsing, men ændrer ikke hvad der kan måles på hvilke modeller.

### 9.3 Sprog-detektion og dens grænse

Sprog-detektion på sporet (for eksempel langdetect) er upålidelig på korte stykker og på kode- og matematik-tunge spor, og overrapporterer derfor skift hvis man kører den naivt linje for linje. Vi måler primært sprog og skift-antal med en mere varsom metode end linje-for-linje, og rapporterer skift-tallet med forbehold for målestøj.

### 9.4 Den kvalitative læse-metode: dommer på originalsproget

Den kvalitative akse har en sprogbarriere der skal håndteres eksplicit: alle de frontier-modeller der eksponerer det rå spor er kinesiske, så sporene er på kinesisk. Tre veje blev overvejet, og valget er bevidst.

**Tving engelsk reasoning: forkastet som læse-vej.** At påtvinge tænke-sproget er ikke neutral forbehandling, det ændrer netop det vi måler. Qi et al. har det i titlen: at kontrollere tænke-sproget koster accuracy. EfficientXLang viste at ikke-engelsk reasoning er adfærdsmæssigt anderledes, ikke kun anderledes tokeniseret. Tving-engelsk hører derfor hjemme som en separat eksperimentbetingelse (arbitrage, afsnit 11), ikke som den linse baseline læses igennem. Bruger man den som læse-omvej, kollapser baseline og indgreb til ét, og sammenligningen forsvinder.

**Oversættelse: kun til stikprøver.** Maskinoversættelse glatter et råt spor ud og rammer netop redundans, usammenhæng og sprogskift, altså de kvalitetssignaler vi vil måle. Oversætter man et sprogskifte-punkt, kan man slette selve skiftet. Oversættelse bruges derfor kun til stikprøve-kontrol, ikke som primær vej.

**Dommer på originalen: den valgte metode.** To dommer-modeller scorer det rå spor på dets eget sprog efter en struktureret rubrik (redundans, intern sammenhæng, sprog-konsistens), og rapporterer sprogskift frem for at slette dem. Den primære dommer er **MiniMax**, valgt fordi den ikke selv er i det scorede panel (så den dømmer ikke sine egne spor) og læser kinesisk indfødt. Den anden dommer er **Gemini 3.1 Pro**, valgt fra en anden afstamning så enigheden mellem en kinesisk og en vestlig dommer bliver et stærkere validitetssignal end to dommere fra samme region. Begge er uden for det scorede panel. Deres indbyrdes enighed rapporteres som mål for dommernes pålidelighed.

To forbehold gør valget holdbart frem for tvivlsomt. **Kapacitet:** MiniMax ligger under frontier og dømmer modeller der scorer højere end den selv. Det ville være en svaghed hvis vi målte korrekthed, men vi måler legibilitet, altså om sporet er læseligt, redundant eller skifter sprog, og det kræver ikke at dommeren kan ud-ræsonnere panelet, kun at den kan læse og bedømme overfladen. Det er endnu en grund til at legibilitet-mod-faithfulness-firewallen ikke er pedanteri. **Lignende skævhed:** MiniMax er selv kinesisk, ligesom tre af de dømte modeller, hvilket kan give en familie-affinitet. Den krydsregionale anden dommer er netop modtrækket mod det.

Det ærlige hovedforbehold står stadig: man kan ikke fuldt revidere en dommer på indhold man ikke selv kan læse. Det er en grænse, ikke en fejl, og den ligger allerede bag legibilitets-firewallen, fordi det er dommerens læsning vi måler, ikke en grundsandhed.

**Gemma som revisions-anker.** Gemmas spor er læsbare for os (engelsk, og dansk på dansk-domæne-opgaver). Vi validerer derfor dommerens opførsel på Gemma-spor vi selv kan kontrollere, og kan så stole mere på dommeren når den læser de kinesiske spor. Det er den anden grund til at Gemma er med i den kvalitative analyse, ud over tokenizer-rollen. Andre engelsk-læsbare rå spor på mellemklasse-niveau (gpt-oss, Llama-familien) kan bruges som supplerende ankre.

**Et fund gemt i barrieren.** På frontier-niveau er de eneste ræsonnementer man overhovedet kan se på et sprog en europæisk operatør ikke kan læse. Engelsk-læsbare rå spor findes kun i mellemklassen. Det strammer suverænitets-tesen et hak: reel monitorerbarhed for en dansk aktør kræver ikke bare en åben model, men en åben model der ræsonnerer på et sprog man kan læse. Det peger lige tilbage på hele projektet, europæisk sprog i selve tænkefasen.

### 9.5 Hvis vi vil sige faithfulness, ikke kun legibilitet

Vil vi udtale os om faithfulness, kræver det et interventionsdesign, ikke bare en dommer der læser spor. Den etablerede metode (Turpin, Lanham): stil modellen et spørgsmål, noter svaret, gentag spørgsmålet med et indlejret signal der peger mod et forkert svar, og se om svaret skifter, og om sporet nævner signalet. Skifter svaret uden at sporet nævner årsagen, er sporet utrofast. Det er en tungere maskine, og i første omgang holder vi os til legibilitet og mærker den som sådan. Interventionsdesignet er en mulig anden fase.

---

## 10. Hvad et rent resultat ser ud som

Et forsvarligt udfald af forsøget lyder cirka sådan: på tværs af fem modeller og ti opgavetyper udgør reasoning en målt andel X til Y procent af output-tokenne på de svære opgaver, og denne andel er usynlig for brugeren på de lukkede modeller. Modeller med sammenlignelig kvalitet adskiller sig med en faktor Z i reasoning-forbrug. På de åbne modeller optræder dansk i tænkefasen i et omfang vi måler direkte, hvilket gør den danske tokeniserings-overhead relevant også her.

Hvad resultatet **ikke** siger: at den effektive model tænker bedre (kun at den bruger færre tokens), at sporet er en sand gengivelse af beregningen (kun at det er mere eller mindre legibelt), eller at en dansk tokenizer ville hæve kvaliteten (kun at den ville sænke token-tallet på det dansk der optræder).

**Den dybeste grænse: vi måler ikke reasoning mod memorering.** Selv korrekthed beviser ikke at en model ræsonnerer. En model kan ramme det rigtige svar fordi mønstret allerede ligger i vægtene fra træningsdataen, ikke fordi den traverserer et problem. Hodel et al. (2024) viste det skarpt: skifter man et analogi-problem fra et velkendt alfabet til et syntetisk, hvor udenadslære ikke kan hjælpe, kollapser en stærk model, mens mennesker ikke gør. Det fortalte os at meget af det der ligner reasoning er memorering på en genkendelig overflade. At adskille de to kræver enten et kontrafaktisk design som Hodels, der fjerner det memorerbare, eller et interventionsdesign som Turpins (2023), der forstyrrer inputtet og ser om sporet er ærligt om det. Begge er selvstændige forskningsfelter, og forsøget her gør ingen af delene. Vi måler økonomi, legibilitet og valgfrit korrekthed. Vi udtaler os ikke om hvorvidt et spor er ægte ræsonnement eller for show. Det er den citerede grænse, og den ligger på linje med vores firewall mellem legibilitet og faithfulness.

Den ærlighed er ikke en svaghed ved forsøget. Den er grunden til at tallene holder.

---

## 11. Kobling til tokenizer-tesen og til suverænitet

To eksperimenter ligger i forlængelse og trækker i hver sin retning, hvilket forsøget kan afgøre frem for at antage:

- **Tving engelsk reasoning.** Lad modellen tænke på engelsk og kun svare på dansk, og mål token-besparelsen i tænkefasen. Hvis den er stor uden kvalitetstab, peger det mod: bare lad modellen tænke på engelsk, og optimér kun det danske svar. Det krymper tokenizerens værdi på reasoning-siden.
- **Dansk i sporet.** Hvis modellen derimod tvinges til dansk inde i sit ræsonnement på dansk-domæne-opgaver, rammer overhead'en tænkefasen, og en dansk tokenizer har værdi også her.

Hvilken der gælder for Gemma på dansk er empirisk, og EfficientXLang viser at retningen ikke er givet på forhånd. Forsøget afgør det.

Suverænitets-koblingen er den dybeste pointe. Den kvalitative akse kan kun køres på modeller der eksponerer sporet, og det er de åbne, selvhostede. Forbrugs-suverænitet (du styrer hvor meget modellen tænker og betaler for) og monitorerings-suverænitet (du kan se hvad den tænker) er den samme kategori set fra to vinkler, og begge findes kun på den åbne side. Det er et governance-argument oven på token-økonomi-argumentet, og det taler til en CISO eller DPO, ikke kun en CFO.

---

## 12. Kildegrundlag

Alle nedenstående er verificeret mod primærkilden.

- **Token-effektivitet som benchmark-dimension:** OckBench, *Measuring the Efficiency of LLM Reasoning*, arXiv:2511.05722 (2025).
- **Krydslingvistisk reasoning-effektivitet:** Ahuja et al., *EfficientXLang*, Microsoft Research, arXiv:2507.00246 (2025).
- **Trin-for-trin metrik-suite:** Golovneva et al., *ROSCOE*, arXiv:2212.07919 (2022).
- **CoT-overvågbarhed (positionspapir):** Korbak et al., *Chain of Thought Monitorability*, arXiv:2507.11473 (2025).
- **Operationalisering af overvågbarhed:** Meek et al., *Measuring Chain-of-Thought Monitorability Through Faithfulness and Verbosity*, arXiv:2510.27378 (2025).
- **Faithfulness-måling:** Lanham et al., arXiv:2307.13702 (2023); Turpin et al. (2023).
- **Reasoning mod memorering (kontrafaktisk):** Hodel et al. (2024). *Eksakt reference og arXiv-ID bekræftes mod primærkilden før citering.*
- **Reasoning-tokens som tilstand, ikke narrativ:** Levy et al., *State over Tokens*, arXiv:2512.12777 (2025).
- **Tænke-tokens som informations-toppe:** Qian et al., arXiv:2506.02867 (2025).
- **CoT og seriel beregning:** Li et al., *Chain of Thought Empowers Transformers to Solve Inherently Serial Problems* (2024).
- **Sprogskat-fundamentet:** Nowable, *The Great Token Test* (2026); Ovcharov, arXiv:2605.24718 (2026).

*Token-fordelingsprocenter, model-specifikationer for 2026-modeller, og benchmark-navne uden for listen ovenfor behandles som ubekræftede indtil verificeret.*
