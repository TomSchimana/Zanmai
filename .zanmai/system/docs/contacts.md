[← Zanmai Documentation](index.md)

# People and organisations

How Zanmai keeps track of who is who, and why they are not filed like topics.

## One note per person, one per organisation

People live in `inbox/contacts/people`, organisations in `inbox/contacts/organizations`, one note each. The fields at the top of the note hold the structured facts, role, organisation, email, phone, and the body is for whatever you want to write about them.

They sit apart from your themes because a person is not a subject. A trip is a subject, and the people on it are people. Everything else points at them with a link, which is what lets you ask who was involved in something and get an answer.

A person and an organisation know about each other in both directions: the person's note names the organisation and links to it, the organisation's note lists its people. That is the one place Zanmai insists on links going both ways; everywhere else linking is optional.

## You are a contact too

Your own entry is a normal contact note, marked as yours by a pointer in your profile rather than by a flag inside the note. That is the address-book approach: every name is a card, and one card is marked as you.

Keeping the pointer in one place means your name can change without two notes both claiming to be you.

The split is worth knowing. Your profile holds settings, your contact note holds you: persistent notes about how you want to be worked with, your writing style, things you corrected, live in the contact note under their own headings.

Setup creates your entry with only what you gave it, usually name, language and perhaps email. Everything else, birthday, phone, address, role, is added later when you mention it or when something actually needs it, for instance a booking that wants a phone number. Zanmai keeps a quiet reminder that the option exists rather than handing you a form.

## When one gets created

Mention someone for the first time and Zanmai asks whether to keep them. During an import it is less hesitant: names found in the material get a short entry each, with a link back to the exact file they came from, because otherwise an import leaves a trail of names that lead nowhere.

Names in your daily notes are treated more carefully. Mentioned once, a name stays text. A name that keeps coming back is offered as a contact, since recurrence is the signal that it will be referenced again.

## When not to create one

A name is not worth its own note just for being mentioned. The test is whether it will be referenced from more than one place, or whether there is structured information worth keeping: an email, a role, an organisation. If neither, the name stays in the text where you wrote it.

Contact notes are also not the place for meeting notes, project notes or trip records. Those belong to their subject and link back to the people involved.

## Related

- [How the vault is organised](folder-architecture.md), where contacts sit in the whole
- [Importing and filing material](importing.md), how contacts appear during an import

---

[← Back to the documentation index](index.md)
