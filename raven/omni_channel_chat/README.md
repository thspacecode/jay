## Feature

### Messaging

|             | Line | Facebook |
|-------------|------|----------|
| Incoming    |      |          |
|   Message   |      |          |
|     Text    | Y    | Y        |
|     Image   | Y    | Y        |
|     File    | Y    | Y        |
|     Sticker | TODO | Y        |
|   Feature   |      |          |
|     Reply   | TODO | TODO     |
| Outgoing    |      |          |
|   Message   |      |          |
|     Text    | Y    | Y        |
|     Image   | *1   | *1       |
|     File    | *1   | *1       |
|   Feature   |      |          |
|     Reply   | TODO | TODO     |

**Remark**

1. Public / Private file has to be handle properly, currently files upload to raven will be private file but chat required it to be private

## TODO

### UX/UI

- [ ] Create Omni-Channel Chat interface for mobile

### Provider

- [ ] Instagram
- [ ] WhatsApp

### Misc

- [ ] Outgoing messages needs message id so we could reply to it properly
- [x] Provider from social login has to change to use provider id, using just "facebook" or "line" will cause error when there are more than 1 provider per each provider (prefix like `OCC_` should be add to provider)
- [x] On BaseMessage `provider` should be change to `provider_id`
- [ ] Create inject interface for connector class